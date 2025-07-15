import logging

import ccxt.async_support as ccxt
import pandas as pd
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    BIT2ME_MAKER_AND_TAKER_FEES_SUM,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem

logger = logging.getLogger(__name__)


class OrdersAnalyticsService(metaclass=SingletonMeta):
    def __init__(
        self,
        bit2me_remote_service: Bit2MeRemoteService,
        ccxt_remote_service: CcxtRemoteService,
        stop_loss_percent_service: StopLossPercentService,
        crypto_analytics_service: CryptoAnalyticsService,
    ) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = bit2me_remote_service
        self._ccxt_remote_service = ccxt_remote_service
        self._stop_loss_percent_service = stop_loss_percent_service
        self._crypto_analytics_service = crypto_analytics_service
        self._exchange = self._ccxt_remote_service.get_exchange()

    async def calculate_all_limit_sell_order_guard_metrics(
        self, *, symbol: str | None = None
    ) -> list[LimitSellOrderGuardMetrics]:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_sell_orders = await self._bit2me_remote_service.get_pending_sell_orders(client=client)
            opened_sell_orders = [
                sell_order
                for sell_order in opened_sell_orders
                if symbol is None or len(symbol) <= 0 or sell_order.symbol.lower().startswith(symbol.lower())
            ]
            async with self._exchange as exchange:
                technical_indicators_by_symbol = await self._calculate_technical_indicators_by_opened_sell_orders(
                    opened_sell_orders, client=client, exchange=exchange
                )
                previous_used_buy_trade_ids: set[str] = set()
                ret = []
                for sell_order in opened_sell_orders:
                    guard_metrics, previous_used_buy_trade_ids = await self.calculate_guard_metrics_by_sell_order(
                        sell_order,
                        technical_indicators=technical_indicators_by_symbol[sell_order.symbol],
                        previous_used_buy_trade_ids=previous_used_buy_trade_ids,
                        client=client,
                    )
                    ret.append(guard_metrics)
                return ret

    async def calculate_guard_metrics_by_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        *,
        technical_indicators: pd.DataFrame | None = None,
        previous_used_buy_trade_ids: set[str] = set(),
        client: AsyncClient | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> tuple[LimitSellOrderGuardMetrics, set[str]]:
        ndigits = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE)
        if technical_indicators is None:
            technical_indicators = await self._crypto_analytics_service.calculate_technical_indicators(
                sell_order.symbol, client=client, exchange=exchange
            )
        (avg_buy_price, previous_used_buy_trade_ids) = await self._calculate_correlated_avg_buy_price(
            sell_order, previous_used_buy_trade_ids, client=client
        )
        (safeguard_stop_price, stop_loss_percent_item) = await self._calculate_safeguard_stop_price(
            sell_order, avg_buy_price
        )
        (suggested_safeguard_stop_price, atr_value, closing_price) = self._calculate_suggested_safeguard_stop_price(
            sell_order, avg_buy_price, technical_indicators=technical_indicators
        )
        suggested_stop_loss_percent_value = round(
            (1 - (suggested_safeguard_stop_price / avg_buy_price)) * 100, ndigits=ndigits
        )
        (suggested_take_profit_limit_price, *_) = self._calculate_suggested_take_profit_limit_price(
            sell_order, avg_buy_price, technical_indicators=technical_indicators
        )
        guard_metrics = LimitSellOrderGuardMetrics(
            sell_order=sell_order,
            avg_buy_price=avg_buy_price,
            break_even_price=round(self._calculate_break_even_price(sell_order, avg_buy_price), ndigits=ndigits),
            stop_loss_percent_value=stop_loss_percent_item.value,
            safeguard_stop_price=safeguard_stop_price,
            current_attr_value=round(atr_value, ndigits=ndigits),
            closing_price=closing_price,
            suggested_safeguard_stop_price=suggested_safeguard_stop_price,
            suggested_stop_loss_percent_value=suggested_stop_loss_percent_value,
            suggested_take_profit_limit_price=suggested_take_profit_limit_price,
        )
        return (guard_metrics, previous_used_buy_trade_ids)

    async def find_stop_loss_percent_by_sell_order(
        self, sell_order: Bit2MeOrderDto
    ) -> tuple[StopLossPercentItem, float]:
        crypto_currency_symbol = sell_order.symbol.split("/")[0].strip().upper()
        stop_loss_percent_item = await self._stop_loss_percent_service.find_stop_loss_percent_by_symbol(
            symbol=crypto_currency_symbol
        )
        stop_loss_percent_decimal_value = stop_loss_percent_item.value / 100
        return stop_loss_percent_item, stop_loss_percent_decimal_value

    async def _calculate_correlated_avg_buy_price(
        self,
        sell_order: Bit2MeOrderDto,
        previous_used_buy_trade_ids: set[str] = set(),
        *,
        client: AsyncClient | None = None,
    ) -> tuple[float, set[str]]:
        last_buy_trades = await self._bit2me_remote_service.get_trades(
            side="buy", symbol=sell_order.symbol, client=client
        )
        correlated_filled_buy_trades = self._get_correlated_filled_buy_trades(
            sell_order, previous_used_buy_trade_ids, last_buy_trades, use_previous_trades=False
        )
        if not correlated_filled_buy_trades:
            correlated_filled_buy_trades = self._get_correlated_filled_buy_trades(
                sell_order, previous_used_buy_trade_ids, last_buy_trades, use_previous_trades=True
            )
        numerator = sum([o.price * o.amount for o in correlated_filled_buy_trades])
        denominator = sum([o.amount for o in correlated_filled_buy_trades])
        avg_buy_price = round(
            numerator / denominator,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        return avg_buy_price, previous_used_buy_trade_ids

    def _get_correlated_filled_buy_trades(
        self,
        sell_order: Bit2MeOrderDto,
        previous_used_buy_trade_ids: set[str],
        buy_trades: list[Bit2MeTradeDto],
        *,
        use_previous_trades: bool = False,
    ) -> list[Bit2MeTradeDto]:
        idx, sum_order_amount = 0, 0.0
        correlated_filled_buy_trades = []
        while sum_order_amount < sell_order.order_amount and idx < len(buy_trades):
            current_buy_trade = buy_trades[idx]
            if use_previous_trades or current_buy_trade.id not in previous_used_buy_trade_ids:
                correlated_filled_buy_trades.append(current_buy_trade)
                sum_order_amount += current_buy_trade.amount
            idx += 1
        previous_used_buy_trade_ids.update([o.id for o in correlated_filled_buy_trades])
        return correlated_filled_buy_trades

    async def _calculate_safeguard_stop_price(
        self, sell_order: Bit2MeOrderDto, avg_buy_price: float
    ) -> tuple[float, StopLossPercentItem]:
        (stop_loss_percent_item, stop_loss_percent_decimal_value) = await self.find_stop_loss_percent_by_sell_order(
            sell_order
        )
        safeguard_stop_price = round(
            avg_buy_price * (1 - stop_loss_percent_decimal_value),
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        return safeguard_stop_price, stop_loss_percent_item

    def _calculate_suggested_safeguard_stop_price(
        self, sell_order: Bit2MeOrderDto, avg_buy_price: float, technical_indicators: pd.DataFrame
    ) -> tuple[float, float, float]:
        last = technical_indicators.iloc[CandleStickEnum.LAST]  # Last confirmed candle
        closing_price = last["close"]
        atr_value = last["atr"]
        suggested_safeguard_stop_price = round(
            avg_buy_price - (last["atr"] * self._configuration_properties.suggested_stop_loss_atr_multiplier),
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        return suggested_safeguard_stop_price, atr_value, closing_price

    def _calculate_suggested_take_profit_limit_price(
        self, sell_order: Bit2MeOrderDto, avg_buy_price: float, technical_indicators: pd.DataFrame
    ) -> tuple[float, float]:
        last = technical_indicators.iloc[CandleStickEnum.LAST]  # Last confirmed candle
        atr_value = last["atr"]
        suggested_safeguard_stop_price = round(
            avg_buy_price + (last["atr"] * self._configuration_properties.suggested_take_profit_atr_multiplier),
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        return suggested_safeguard_stop_price, atr_value

    def _calculate_break_even_price(self, sell_order: Bit2MeOrderDto, avg_buy_price: float) -> float:
        break_even_price = round(
            avg_buy_price * (1.0 + BIT2ME_MAKER_AND_TAKER_FEES_SUM),
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        return break_even_price

    async def _calculate_technical_indicators_by_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient, exchange: ccxt.Exchange
    ) -> dict[str, pd.DataFrame]:
        opened_sell_order_symbols = set([sell_order.symbol for sell_order in opened_sell_orders])

        technical_indicators_by_symbol = {
            symbol: await self._crypto_analytics_service.calculate_technical_indicators(
                symbol, client=client, exchange=exchange
            )
            for symbol in opened_sell_order_symbols
        }
        return technical_indicators_by_symbol
