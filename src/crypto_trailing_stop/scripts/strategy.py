# At the top of scripts/main.py

from backtesting import Strategy

from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.scripts.constants import DEFAULT_TRADING_MARKET_CONFIG


class SignalStrategy(Strategy):
    """
    Smart strategy that precisely replicates the entry and nuanced exit logic
    of the production bot.
    """

    # Parameters that will be set by the backtest engine
    enable_tp: bool = False
    atr_sl_multiplier: float = 2.5
    atr_tp_multiplier: float = 3.5
    simulated_bs_config: BuySellSignalsConfigItem = None
    analytics_service: CryptoAnalyticsService = None

    def init(self):
        # Make sure all necessary data is available as a variable
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=None,
            ccxt_remote_service=self.analytics_service._ccxt_remote_service,
            stop_loss_percent_service=None,
            buy_sell_signals_config_service=None,
            crypto_analytics_service=self.analytics_service,
        )
        self.atr = self.I(lambda x: x, self.data.atr)
        self.macd_hist = self.I(lambda x: x, self.data.macd_hist)
        self.prev_macd_hist = self.I(lambda x: x, self.data.prev_macd_hist)

    def next(self):
        # 2. Rename the index of just this one Series to lowercase
        candlestick = self.data.df.iloc[-1].rename(
            {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            symbol=self.simulated_bs_config.symbol,
            candlestick=candlestick,
            trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
        )
        if not self.position and self.data.buy_signal[-1]:
            suggested_stop_loss = self._orders_analytics_service._calculate_suggested_stop_loss_percent_value(
                self.data.Close[-1],
                buy_sell_signals_config=self.simulated_bs_config,
                last_candle_market_metrics=last_candle_market_metrics,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            sl_price = self._orders_analytics_service._calculate_suggested_safeguard_stop_price(
                self.data.Close[-1],
                suggested_stop_loss_percent_value=suggested_stop_loss,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            tp_price = None
            if self.enable_tp:
                tp_price = self._orders_analytics_service._calculate_suggested_take_profit_limit_price(
                    self.data.Close[-1],
                    buy_sell_signals_config=self.simulated_bs_config,
                    last_candle_market_metrics=last_candle_market_metrics,
                    trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
                )
            self.buy(sl=sl_price, tp=tp_price)

        if self.position:
            # First, check if we are at or above break-even
            # break_even_price = self._orders_analytics_service._calculate_break_even_price(
            #     self.trades[-1].entry_price, trading_market_config=DEFAULT_TRADING_MARKET_CONFIG
            # )
            is_above_breakeven = self.data.Close[-1] >= self.trades[-1].entry_price
            if is_above_breakeven:
                # Condition A: Proactive exit on BEARISH DIVERGENCE
                exit_on_divergence = self.data.bearish_divergence[-1]
                # Condition B: Confirmed exit on SELL SIGNAL
                # Replicates the production logic: signal must be present AND
                # MACD histogram must be negative and accelerating downwards.
                exit_on_sell_signal = (
                    self.data.sell_signal[-1]
                    and self.macd_hist[-1] < 0
                    and self.macd_hist[-1] < self.prev_macd_hist[-1]
                )
                # If either exit condition is met, close the position
                if exit_on_divergence or exit_on_sell_signal:
                    self.position.close()
