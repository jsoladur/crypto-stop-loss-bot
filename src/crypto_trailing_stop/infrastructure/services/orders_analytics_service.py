import logging
import math
from typing import Any

import ccxt.async_support as ccxt
import numpy as np
import pandas as pd

from crypto_trailing_stop.commons.constants import STOP_LOSS_PERCENT_BUFFER, STOP_LOSS_STEPS_VALUE_LIST
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.order import Order
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_tickers import SymbolTickers
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.trade import Trade
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


class OrdersAnalyticsService(AbstractService):
    def __init__(
        self,
        operating_exchange_service: AbstractOperatingExchangeService,
        ccxt_remote_service: CcxtRemoteService,
        stop_loss_percent_service: StopLossPercentService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
        crypto_analytics_service: CryptoAnalyticsService,
    ) -> None:
        self._operating_exchange_service = operating_exchange_service
        self._ccxt_remote_service = ccxt_remote_service
        self._stop_loss_percent_service = stop_loss_percent_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._crypto_analytics_service = crypto_analytics_service
        self._exchange = self._ccxt_remote_service.get_exchange()

    async def calculate_all_limit_sell_order_guard_metrics(
        self, *, symbol: str | None = None
    ) -> list[LimitSellOrderGuardMetrics]:
        async with await self._operating_exchange_service.get_client() as client:
            opened_sell_orders = await self._operating_exchange_service.get_pending_sell_orders(client=client)
            opened_sell_orders = [
                sell_order
                for sell_order in opened_sell_orders
                if symbol is None or len(symbol) <= 0 or sell_order.symbol.lower().startswith(symbol.lower())
            ]
            ret = []
            if opened_sell_orders is not None and len(opened_sell_orders) > 0:
                current_tickers_by_symbol: dict[str, SymbolTickers] = await self._fetch_tickers_for_open_sell_orders(
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
        sell_order: Order,
        *,
        tickers: SymbolTickers | None = None,
        buy_sell_signals_config: BuySellSignalsConfigItem | None = None,
        technical_indicators: pd.DataFrame | None = None,
        last_buy_trades: list[Trade] | None = None,
        previous_used_buy_trades: dict[str, float] = {},
        client: Any | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> tuple[LimitSellOrderGuardMetrics, set[str]]:
        trading_market_config = await self._operating_exchange_service.get_trading_market_config_by_symbol(
            sell_order.symbol, client=client
        )
        if tickers is None:
            tickers = await self._operating_exchange_service.get_single_tickers_by_symbol(
                sell_order.symbol, client=client
            )
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
            safeguard_stop_price=safeguard_stop_price,
            current_attr_value=rounded_last_candle_market_metrics.atr,
            current_atr_percent=rounded_last_candle_market_metrics.atr_percent,
            closing_price=last_candle_market_metrics.closing_price,
            suggested_stop_loss_percent_value=suggested_stop_loss_percent_value,
            suggested_safeguard_stop_price=suggested_safeguard_stop_price,
            suggested_take_profit_limit_price=suggested_take_profit_limit_price,
        )
        return (guard_metrics, previous_used_buy_trades)

    async def find_stop_loss_percent_by_sell_order(self, sell_order: Order) -> tuple[StopLossPercentItem, float]:
        crypto_currency_symbol = sell_order.symbol.split("/")[0].strip().upper()
        stop_loss_percent_item = await self._stop_loss_percent_service.find_symbol(symbol=crypto_currency_symbol)
        stop_loss_percent_decimal_value = stop_loss_percent_item.value / 100
        return stop_loss_percent_item, stop_loss_percent_decimal_value

    async def _calculate_correlated_avg_buy_price(
        self,
        sell_order: Order,
        previous_used_buy_trades: dict[str, float] = {},
        *,
        trading_market_config: SymbolMarketConfig,
        last_buy_trades: list[Trade] | None = None,
        client: Any | None = None,
    ) -> tuple[float, set[str]]:
        if last_buy_trades is None or len(last_buy_trades) <= 0:
            last_buy_trades = await self._operating_exchange_service.get_trades(
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

    def _calculate_break_even_price(self, avg_buy_price: float, *, trading_market_config: SymbolMarketConfig) -> float:
        taker_fees = self._operating_exchange_service.get_taker_fee()
        break_even_price = round(
            avg_buy_price * ((1.0 + taker_fees) / (1.0 - taker_fees)), ndigits=trading_market_config.price_precision
        )
        return break_even_price

    def _calculate_current_profit(
        self,
        sell_order: Order,
        avg_buy_price: float,
        tickers: SymbolTickers,
        *,
        trading_market_config: SymbolMarketConfig,
    ) -> float:
        ret = round(
            (tickers.bid_or_close - avg_buy_price) * sell_order.amount, ndigits=trading_market_config.price_precision
        )
        return ret

    def _calculate_net_revenue(
        self,
        sell_order: Order,
        break_even_price: float,
        tickers: SymbolTickers,
        *,
        trading_market_config: SymbolMarketConfig,
    ) -> float:
        ret = round(
            (tickers.bid_or_close - break_even_price) * sell_order.amount, ndigits=trading_market_config.price_precision
        )
        return ret

    def _get_correlated_filled_buy_trades(
        self, sell_order: Order, buy_trades: list[Trade], *, previous_used_buy_trades: dict[str, float] = {}
    ) -> list[tuple[Trade, float]]:
        """Calculate the correlated buy trades related to the sell order passed as argument.

        Args:
            sell_order (Order): Sell order
            buy_trades (list[Trade]): Buy trades
            previous_used_buy_trades (dict[str, float]): Previous used buy trades

        Returns:
            list[tuple[Trade, float]]: Each trade used alongside with the used amount
        """
        idx, filled_sell_amount = 0, 0.0
        correlated_filled_buy_trades = []
        while filled_sell_amount < sell_order.amount and idx < len(buy_trades):
            current_buy_trade = buy_trades[idx]
            # Calculate how much we can get from this trade
            previous_used_trade_amount = previous_used_buy_trades.setdefault(current_buy_trade.id, 0.0)
            remaining_trade_amount = current_buy_trade.amount_after_fee - previous_used_trade_amount
            if remaining_trade_amount > 0:
                remaining_sell_amount = sell_order.amount - filled_sell_amount
                if remaining_sell_amount >= remaining_trade_amount:
                    filled_sell_amount += remaining_trade_amount
                    correlated_filled_buy_trades.append((current_buy_trade, remaining_trade_amount))
                    previous_used_buy_trades[current_buy_trade.id] += remaining_trade_amount
                else:
                    filled_sell_amount += remaining_sell_amount
                    correlated_filled_buy_trades.append((current_buy_trade, remaining_sell_amount))
                    previous_used_buy_trades[current_buy_trade.id] += remaining_sell_amount
            idx += 1
        return correlated_filled_buy_trades

    async def _calculate_safeguard_stop_price(
        self, sell_order: Order, avg_buy_price: float, *, trading_market_config: SymbolMarketConfig
    ) -> tuple[float, float]:
        (stop_loss_percent_item, stop_loss_percent_decimal_value) = await self.find_stop_loss_percent_by_sell_order(
            sell_order
        )
        safeguard_stop_price = round(
            avg_buy_price * (1 - stop_loss_percent_decimal_value), ndigits=trading_market_config.price_precision
        )
        return safeguard_stop_price, stop_loss_percent_item.value

    def _calculate_suggested_stop_loss_percent_value(
        self,
        avg_buy_price: float,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        *,
        last_candle_market_metrics: CryptoMarketMetrics,
        trading_market_config: SymbolMarketConfig,
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
        trading_market_config: SymbolMarketConfig,
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
        trading_market_config: SymbolMarketConfig,
    ) -> float:
        suggested_take_profit_limit_price = round(
            avg_buy_price + (last_candle_market_metrics.atr * buy_sell_signals_config.take_profit_atr_multiplier),
            ndigits=trading_market_config.price_precision,
        )
        return suggested_take_profit_limit_price

    async def _calculate_buy_sell_signals_config_by_opened_sell_orders(
        self, opened_sell_orders: list[Order]
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
        self, opened_sell_orders: list[Order], *, client: Any, exchange: ccxt.Exchange
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
