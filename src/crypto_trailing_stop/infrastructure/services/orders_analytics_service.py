import logging
import math

import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    BIT2ME_TAKER_FEES,
    STOP_LOSS_PERCENT_BUFFER,
    STOP_LOSS_STEPS_VALUE_LIST,
)
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem

logger = logging.getLogger(__name__)


class OrdersAnalyticsService(AbstractService, metaclass=SingletonABCMeta):
    def __init__(
        self,
        bit2me_remote_service: Bit2MeRemoteService,
        ccxt_remote_service: CcxtRemoteService,
        stop_loss_percent_service: StopLossPercentService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
        crypto_analytics_service: CryptoAnalyticsService,
    ) -> None:
        self._bit2me_remote_service = bit2me_remote_service
        self._ccxt_remote_service = ccxt_remote_service
        self._stop_loss_percent_service = stop_loss_percent_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
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
            ret = []
            if opened_sell_orders is not None and len(opened_sell_orders) > 0:
                current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = await self._fetch_tickers_for_open_sell_orders(
                    opened_sell_orders, client=client
                )
                buy_sell_signals_config_by_symbol = await self._calculate_buy_sell_signals_config_by_opened_sell_orders(
                    opened_sell_orders
                )
                last_buy_trades_by_symbol = await self._get_last_buy_trades_by_opened_sell_orders(
                    opened_sell_orders, client=client
                )
                async with self._exchange as exchange:
                    technical_indicators_by_symbol = await self._calculate_technical_indicators_by_opened_sell_orders(
                        opened_sell_orders, client=client, exchange=exchange
                    )
                    previous_used_buy_trades: dict[str, float] = {}
                    for sell_order in opened_sell_orders:
                        crypto_currency, *_ = sell_order.symbol.split("/")
                        guard_metrics, previous_used_buy_trades = await self.calculate_guard_metrics_by_sell_order(
                            sell_order,
                            tickers=current_tickers_by_symbol[sell_order.symbol],
                            buy_sell_signals_config=buy_sell_signals_config_by_symbol[crypto_currency],
                            technical_indicators=technical_indicators_by_symbol[sell_order.symbol],
                            last_buy_trades=last_buy_trades_by_symbol[sell_order.symbol],
                            previous_used_buy_trades=previous_used_buy_trades,
                            client=client,
                        )
                        ret.append(guard_metrics)
            return ret

    async def calculate_guard_metrics_by_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        *,
        tickers: Bit2MeTickersDto | None = None,
        buy_sell_signals_config: BuySellSignalsConfigItem | None = None,
        technical_indicators: pd.DataFrame | None = None,
        last_buy_trades: list[Bit2MeTradeDto] | None = None,
        previous_used_buy_trades: dict[str, float] = {},
        client: AsyncClient | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> tuple[LimitSellOrderGuardMetrics, set[str]]:
        trading_market_config = await self._bit2me_remote_service.get_trading_market_config_by_symbol(
            sell_order.symbol, client=client
        )
        if tickers is None:
            tickers = await self._bit2me_remote_service.get_single_tickers_by_symbol(sell_order.symbol, client=client)
        if buy_sell_signals_config is None:
            crypto_currency, *_ = sell_order.symbol.split("/")
            buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
        if technical_indicators is None:
            technical_indicators, *_ = await self._crypto_analytics_service.calculate_technical_indicators(
                sell_order.symbol, client=client, exchange=exchange
            )
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            sell_order.symbol,
            candlestick=technical_indicators.iloc[CandleStickEnum.LAST],  # Last confirmed candle
            trading_market_config=trading_market_config,
        )
        (avg_buy_price, previous_used_buy_trades) = await self._calculate_correlated_avg_buy_price(
            sell_order,
            previous_used_buy_trades,
            trading_market_config=trading_market_config,
            last_buy_trades=last_buy_trades,
            client=client,
        )
        break_even_price = self._calculate_break_even_price(avg_buy_price, trading_market_config=trading_market_config)
        current_profit = self._calculate_current_profit(
            sell_order, avg_buy_price, tickers, trading_market_config=trading_market_config
        )
        net_revenue = self._calculate_net_revenue(
            sell_order, break_even_price, tickers, trading_market_config=trading_market_config
        )
        (safeguard_stop_price, stop_loss_percent_value) = await self._calculate_safeguard_stop_price(
            sell_order, avg_buy_price, trading_market_config=trading_market_config
        )
        (breathe_safeguard_stop_price, breathe_stop_loss_percent_value) = self._calculate_breathing_safeguards(
            avg_buy_price, stop_loss_percent_value, trading_market_config=trading_market_config
        )
        suggested_stop_loss_percent_value = self._calculate_suggested_stop_loss_percent_value(
            avg_buy_price,
            buy_sell_signals_config=buy_sell_signals_config,
            last_candle_market_metrics=last_candle_market_metrics,
            trading_market_config=trading_market_config,
        )
        suggested_safeguard_stop_price = self._calculate_suggested_safeguard_stop_price(
            avg_buy_price, suggested_stop_loss_percent_value, trading_market_config=trading_market_config
        )
        suggested_take_profit_limit_price = self._calculate_suggested_take_profit_limit_price(
            avg_buy_price,
            buy_sell_signals_config=buy_sell_signals_config,
            last_candle_market_metrics=last_candle_market_metrics,
            trading_market_config=trading_market_config,
        )
        rounded_last_candle_market_metrics = last_candle_market_metrics.rounded(trading_market_config)
        guard_metrics = LimitSellOrderGuardMetrics(
            sell_order=sell_order,
            current_price=tickers.bid_or_close,
            avg_buy_price=avg_buy_price,
            break_even_price=break_even_price,
            current_profit=current_profit,
            net_revenue=net_revenue,
            stop_loss_percent_value=stop_loss_percent_value,
            breathe_stop_loss_percent_value=breathe_stop_loss_percent_value,
            safeguard_stop_price=safeguard_stop_price,
            breathe_safeguard_stop_price=breathe_safeguard_stop_price,
            current_attr_value=rounded_last_candle_market_metrics.atr,
            current_atr_percent=rounded_last_candle_market_metrics.atr_percent,
            closing_price=last_candle_market_metrics.closing_price,
            suggested_stop_loss_percent_value=suggested_stop_loss_percent_value,
            suggested_safeguard_stop_price=suggested_safeguard_stop_price,
            suggested_take_profit_limit_price=suggested_take_profit_limit_price,
        )
        return (guard_metrics, previous_used_buy_trades)

    async def find_stop_loss_percent_by_sell_order(
        self, sell_order: Bit2MeOrderDto
    ) -> tuple[StopLossPercentItem, float]:
        crypto_currency_symbol = sell_order.symbol.split("/")[0].strip().upper()
        stop_loss_percent_item = await self._stop_loss_percent_service.find_symbol(symbol=crypto_currency_symbol)
        stop_loss_percent_decimal_value = stop_loss_percent_item.value / 100
        return stop_loss_percent_item, stop_loss_percent_decimal_value

    async def _calculate_correlated_avg_buy_price(
        self,
        sell_order: Bit2MeOrderDto,
        previous_used_buy_trades: dict[str, float] = {},
        *,
        trading_market_config: Bit2MeMarketConfigDto,
        last_buy_trades: list[Bit2MeTradeDto] | None = None,
        client: AsyncClient | None = None,
    ) -> tuple[float, set[str]]:
        if last_buy_trades is None or len(last_buy_trades) <= 0:
            last_buy_trades = await self._bit2me_remote_service.get_trades(
                side="buy", symbol=sell_order.symbol, client=client
            )
        correlated_filled_buy_trades = self._get_correlated_filled_buy_trades(
            sell_order, last_buy_trades, previous_used_buy_trades=previous_used_buy_trades
        )
        if not correlated_filled_buy_trades:
            correlated_filled_buy_trades = self._get_correlated_filled_buy_trades(
                sell_order, last_buy_trades, previous_used_buy_trades={}
            )
        numerator = sum([buy_trade.price * used_amount for buy_trade, used_amount in correlated_filled_buy_trades])
        denominator = sum([used_amount for _, used_amount in correlated_filled_buy_trades])
        avg_buy_price = round(numerator / denominator, ndigits=trading_market_config.price_precision)
        return avg_buy_price, previous_used_buy_trades

    def _calculate_break_even_price(
        self, avg_buy_price: float, *, trading_market_config: Bit2MeMarketConfigDto
    ) -> float:
        break_even_price = round(
            avg_buy_price * ((1.0 + BIT2ME_TAKER_FEES) / (1.0 - BIT2ME_TAKER_FEES)),
            ndigits=trading_market_config.price_precision,
        )
        return break_even_price

    def _calculate_current_profit(
        self,
        sell_order: Bit2MeOrderDto,
        avg_buy_price: float,
        tickers: Bit2MeTickersDto,
        *,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> float:
        ret = round(
            (tickers.bid_or_close - avg_buy_price) * sell_order.order_amount,
            ndigits=trading_market_config.price_precision,
        )
        return ret

    def _calculate_net_revenue(
        self,
        sell_order: Bit2MeOrderDto,
        break_even_price: float,
        tickers: Bit2MeTickersDto,
        *,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> float:
        ret = round(
            (tickers.bid_or_close - break_even_price) * sell_order.order_amount,
            ndigits=trading_market_config.price_precision,
        )
        return ret

    def _get_correlated_filled_buy_trades(
        self,
        sell_order: Bit2MeOrderDto,
        buy_trades: list[Bit2MeTradeDto],
        *,
        previous_used_buy_trades: dict[str, float] = {},
    ) -> list[tuple[Bit2MeTradeDto, float]]:
        """Calculate the correlated buy trades related to the sell order passed as argument.

        Args:
            sell_order (Bit2MeOrderDto): Sell order
            buy_trades (list[Bit2MeTradeDto]): Buy trades
            previous_used_buy_trades (dict[str, float]): Previous used buy trades

        Returns:
            list[tuple[Bit2MeTradeDto, float]]: Each trade used alongside with the used amount
        """
        idx, sum_order_amount = 0, 0.0
        correlated_filled_buy_trades = []
        while sum_order_amount < sell_order.order_amount and idx < len(buy_trades):
            current_buy_trade = buy_trades[idx]
            rest_sell_order_amount_to_allocate = sell_order.order_amount - sum_order_amount
            # Calculate how much we can get from this trade
            previous_used_trade_amount = previous_used_buy_trades.setdefault(current_buy_trade.id, 0.0)
            rest_trade_amount_to_allocate = current_buy_trade.amount_after_fee - previous_used_trade_amount
            if rest_trade_amount_to_allocate > 0:
                correlated_filled_buy_trades.append((current_buy_trade, rest_trade_amount_to_allocate))
                sum_order_amount += rest_trade_amount_to_allocate
                if rest_sell_order_amount_to_allocate >= rest_trade_amount_to_allocate:
                    previous_used_buy_trades[current_buy_trade.id] = current_buy_trade.amount_after_fee
                else:
                    previous_used_buy_trades[current_buy_trade.id] += (
                        rest_trade_amount_to_allocate - rest_sell_order_amount_to_allocate
                    )
            idx += 1
        return correlated_filled_buy_trades

    async def _calculate_safeguard_stop_price(
        self, sell_order: Bit2MeOrderDto, avg_buy_price: float, *, trading_market_config: Bit2MeMarketConfigDto
    ) -> tuple[float, float]:
        (stop_loss_percent_item, stop_loss_percent_decimal_value) = await self.find_stop_loss_percent_by_sell_order(
            sell_order
        )
        safeguard_stop_price = round(
            avg_buy_price * (1 - stop_loss_percent_decimal_value), ndigits=trading_market_config.price_precision
        )
        return safeguard_stop_price, stop_loss_percent_item.value

    def _calculate_breathing_safeguards(
        self, avg_buy_price: float, stop_loss_percent_value: float, *, trading_market_config: Bit2MeMarketConfigDto
    ) -> tuple[float, float]:
        # Calculate the Breathe Stop Loss based on the Stop Loss Percent Item
        if stop_loss_percent_value < STOP_LOSS_STEPS_VALUE_LIST[-1]:
            steps = np.array(STOP_LOSS_STEPS_VALUE_LIST)
            # Ensure the Breathe Stop Loss is at least the next step above the calculated Stop Loss
            next_step_value = float(steps[steps > stop_loss_percent_value].min())
            # Increment the Stop Loss at least 0.50% to ensure a gap
            increment_value = max(next_step_value - stop_loss_percent_value, 0.50)
            breathe_stop_loss_percent_value = stop_loss_percent_value + increment_value
        else:
            breathe_stop_loss_percent_value = stop_loss_percent_value

        breathe_stop_loss_decimal_value = breathe_stop_loss_percent_value / 100
        breathe_safeguard_stop_price = round(
            avg_buy_price * (1 - breathe_stop_loss_decimal_value), ndigits=trading_market_config.price_precision
        )
        return breathe_safeguard_stop_price, breathe_stop_loss_percent_value

    def _calculate_suggested_stop_loss_percent_value(
        self,
        avg_buy_price: float,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        *,
        last_candle_market_metrics: CryptoMarketMetrics,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> float:
        first_suggested_safeguard_stop_price = round(
            avg_buy_price - (last_candle_market_metrics.atr * buy_sell_signals_config.stop_loss_atr_multiplier),
            ndigits=trading_market_config.price_precision,
        )
        stop_loss_percent_value = (
            self._ceil_round((1 - (first_suggested_safeguard_stop_price / avg_buy_price)) * 100, ndigits=4)
            + STOP_LOSS_PERCENT_BUFFER
        )
        if stop_loss_percent_value < STOP_LOSS_STEPS_VALUE_LIST[-1]:
            steps = np.array(STOP_LOSS_STEPS_VALUE_LIST)
            # Summing 0.5 to the calculated Stop Loss, to ensure enough gap when ATR is very low!
            stop_loss_percent_value = float(steps[steps >= stop_loss_percent_value].min())
        else:  # Round to 2 decimal place if greater than the last step
            stop_loss_percent_value = self._ceil_round(stop_loss_percent_value, ndigits=2)
        return stop_loss_percent_value

    def _calculate_suggested_safeguard_stop_price(
        self,
        avg_buy_price: float,
        suggested_stop_loss_percent_value: float,
        *,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> float:
        suggested_stop_loss_decimal_value = suggested_stop_loss_percent_value / 100
        suggested_safeguard_stop_price = round(
            avg_buy_price * (1 - suggested_stop_loss_decimal_value), ndigits=trading_market_config.price_precision
        )
        return suggested_safeguard_stop_price

    def _calculate_suggested_take_profit_limit_price(
        self,
        avg_buy_price: float,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        *,
        last_candle_market_metrics: CryptoMarketMetrics,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> float:
        suggested_safeguard_stop_price = round(
            avg_buy_price + (last_candle_market_metrics.atr * buy_sell_signals_config.take_profit_atr_multiplier),
            ndigits=trading_market_config.price_precision,
        )
        return suggested_safeguard_stop_price

    async def _calculate_buy_sell_signals_config_by_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto]
    ) -> dict[str, pd.DataFrame]:
        opened_sell_order_crypto_currencies = set(
            [sell_order.symbol.split("/")[0] for sell_order in opened_sell_orders]
        )
        buy_sell_signals_config_list = await self._buy_sell_signals_config_service.find_by_symbols(
            symbols=opened_sell_order_crypto_currencies
        )
        buy_sell_signals_config_by_symbol = {
            buy_sell_signals_config.symbol: buy_sell_signals_config
            for buy_sell_signals_config in buy_sell_signals_config_list
        }
        return buy_sell_signals_config_by_symbol

    async def _calculate_technical_indicators_by_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient, exchange: ccxt.Exchange
    ) -> dict[str, pd.DataFrame]:
        opened_sell_order_symbols = set([sell_order.symbol for sell_order in opened_sell_orders])
        technical_indicators_by_symbol = {}
        for symbol in opened_sell_order_symbols:
            technical_indicators, *_ = await self._crypto_analytics_service.calculate_technical_indicators(
                symbol, client=client, exchange=exchange
            )
            technical_indicators_by_symbol[symbol] = technical_indicators
        return technical_indicators_by_symbol

    def _ceil_round(self, value: float, *, ndigits: int) -> float:
        factor = 10**ndigits
        return math.ceil(value * factor) / factor
