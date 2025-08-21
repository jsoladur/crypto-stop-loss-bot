import logging

from backtesting import Strategy

from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.scripts.constants import DEFAULT_TRADING_MARKET_CONFIG

logger = logging.getLogger(__name__)


class SignalStrategy(Strategy):
    """
    Smart strategy that precisely replicates the bot's dynamic and separate exit logics.
    """

    # Parameters that will be set by the backtest engine
    enable_tp: bool = False
    simulated_bs_config: BuySellSignalsConfigItem = None
    analytics_service: CryptoAnalyticsService = None

    def init(self):
        # Instantiate the service needed for calculations
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=None,
            ccxt_remote_service=self.analytics_service._ccxt_remote_service,
            stop_loss_percent_service=None,
            buy_sell_signals_config_service=None,
            crypto_analytics_service=self.analytics_service,
        )
        # Map necessary data columns for easy access
        self.atr = self.I(lambda x: x, self.data.atr)
        self.macd_hist = self.I(lambda x: x, self.data.macd_hist)
        self.prev_macd_hist = self.I(lambda x: x, self.data.prev_macd_hist)
        # State variable to remember if a sell signal has occurred
        self.sell_signal_active = False

    def next(self):
        # --- Calculate current candle metrics ONCE at the beginning ---
        candlestick = self.data.df.iloc[-1].rename(
            {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        last_candle_metrics = CryptoMarketMetrics.from_candlestick(
            symbol=self.simulated_bs_config.symbol,
            candlestick=candlestick,
            trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
        )

        # --- Update State ---
        # If a new SELL signal appears, activate our alert state.
        if self.data.sell_signal[-1]:
            self.sell_signal_active = True
        # If a new BUY signal appears, it cancels any old sell alerts.
        elif self.data.buy_signal[-1]:
            self.sell_signal_active = False

        # --- ENTRY LOGIC ---
        # Now uses the pre-calculated 'last_candle_metrics'
        if not self.position and self.data.buy_signal[-1]:
            stop_loss_pct = self._orders_analytics_service._calculate_suggested_stop_loss_percent_value(
                self.data.Close[-1],
                buy_sell_signals_config=self.simulated_bs_config,
                last_candle_market_metrics=last_candle_metrics,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            sl_price = self._orders_analytics_service._calculate_suggested_safeguard_stop_price(
                self.data.Close[-1],
                suggested_stop_loss_percent_value=stop_loss_pct,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            self.buy(sl=sl_price, tp=None)
            # We just bought, so reset any lingering sell signal alert
            self.sell_signal_active = False

        # --- DYNAMIC TRADE MANAGEMENT (ONLY IF A POSITION IS OPEN) ---
        if self.position:
            break_even_price = self._orders_analytics_service._calculate_break_even_price(
                self.trades[-1].entry_price, trading_market_config=DEFAULT_TRADING_MARKET_CONFIG
            )

            # --- Check 1: Dynamic Take-Profit Exit ---
            exit_on_take_profit = False
            if self.enable_tp:
                tp_price = self._orders_analytics_service._calculate_suggested_take_profit_limit_price(
                    self.trades[-1].entry_price,
                    buy_sell_signals_config=self.simulated_bs_config,
                    last_candle_market_metrics=last_candle_metrics,
                    trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
                )
                # A TP exit is valid if the high hits the TP price AND that TP price is above break-even.
                if self.data.High[-1] >= tp_price and tp_price >= break_even_price:
                    exit_on_take_profit = True

            # --- Check 2: Smart Signal Exit (now with memory) ---
            exit_on_signal = False
            if self.data.Close[-1] >= break_even_price:
                # Proactive exit on a NEW divergence
                exit_on_divergence = self.data.bearish_divergence[-1]

                # Exit if our SELL SIGNAL STATE is active AND momentum is confirmed
                exit_on_sell_signal_state = (
                    self.sell_signal_active and self.macd_hist[-1] < 0 and self.macd_hist[-1] < self.prev_macd_hist[-1]
                )

                if exit_on_divergence or exit_on_sell_signal_state:
                    exit_on_signal = True

            # --- Final Exit Decision ---
            if exit_on_take_profit or exit_on_signal:
                self.position.close()
                # Once the position is closed, reset the sell signal alert
                self.sell_signal_active = False
