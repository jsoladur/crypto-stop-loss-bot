import numpy as np

BIT2ME_API_BASE_URL = "https://gateway.bit2me.com"
MEXC_API_BASE_URL = "https://api.mexc.com"

TELEGRAM_REPLY_EXCEPTION_MESSAGE_MAX_LENGTH = 3_000
IDEMPOTENT_HTTP_METHODS = ["GET", "HEAD", "OPTIONS", "TRACE"]
# Backoff status codes for Bit2Me
BIT2ME_RETRYABLE_HTTP_STATUS_CODES = [403, 412, 417, 429, 451, 455, 502, 503, 504]
# Backoff status codes for MEXC
MEXC_RETRYABLE_HTTP_STATUS_CODES = [400, 403, 429, 502, 503, 504]
DEFAULT_DIVERGENCE_WINDOW = 60
DEFAULT_JOB_INTERVAL_SECONDS = 5  # 5 seconds
DEFAULT_TRAILING_STOP_LOSS_PERCENT = 5.0  # Best Spot Loss value intra-day, based on experience
STOP_LOSS_STEPS_VALUE_LIST = np.concatenate(
    (np.arange(0.25, 5.25, 0.25), np.arange(5.50, 10.50, 0.50), np.arange(11, 21, 1))
).tolist()
PERCENT_TO_SELL_LIST = np.arange(25, 125, 25).tolist()
TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD = 0.00025
DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS = 86_400  # 1 day
# Removing number of executions
BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN = [0, 1, 2, 3, 5, 15, 30, 31, 32, 33, 35, 45]
# Event Emitter - Event names
SIGNALS_EVALUATION_RESULT_EVENT_NAME = "signals_evaluation_result"
TRIGGER_BUY_ACTION_EVENT_NAME = "trigger_buy_action"
# Bit2Me Fees
BIT2ME_TAKER_FEES = 0.00259
# MEXC Fees
MEXC_TAKER_FEES = 0.0005
# Auto-Entry Trader
AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST = 25.0
AUTO_ENTRY_TRADER_CONFIG_STEPS_VALUE_LIST = np.arange(0, 105, 5).tolist()
AUTO_ENTRY_TRADER_MAX_ATTEMPS_TO_BUY = 5
AUTO_ENTRY_MARKET_ORDER_SAFETY_FACTOR = 0.995  # 0.5% less to avoid insufficient balance errors
# Limit Sell Order Guard
LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR = 0.98  # 2% security gap to avoid slippage
# Order Analytics magic numbers
STOP_LOSS_PERCENT_BUFFER = 0.75
# Buy Sell Signals Config
EMA_SHORT_MID_PAIRS_AS_TUPLES = [(7, 18), (8, 20), (9, 21)]
SP_TP_PAIRS_AS_TUPLES = [
    (2.5, 3.8),  # RRR: 1.5
    (2.5, 4.0),  # RRR: 1.6
    (2.5, 4.2),  # RRR: 1.7
    (3.0, 4.5),  # RRR: 1.5
    (3.0, 4.8),  # RRR: 1.6
    (3.0, 5.1),  # RRR: 1.7
]
EMA_SHORT_MID_PAIRS = [f"{ema_short}/{ema_mid}" for ema_short, ema_mid in EMA_SHORT_MID_PAIRS_AS_TUPLES]
SP_TP_PAIRS = [f"{sp_percent}/{tp_percent}" for sp_percent, tp_percent in SP_TP_PAIRS_AS_TUPLES]
EMA_LONG_VALUES = [150, 200, 233]
ADX_THRESHOLD_VALUES = [15, 20, 25]
MIN_VOLUME_THRESHOLD_STEP_VALUE = 0.05
MAX_VOLUME_THRESHOLD_STEP_VALUE = 0.25
MIN_VOLUME_THRESHOLD_VALUES = [
    round(min_volume_threshold, ndigits=2)
    for min_volume_threshold in np.arange(0.05, 2.05, MIN_VOLUME_THRESHOLD_STEP_VALUE).tolist()
]
MAX_VOLUME_THRESHOLD_VALUES = [
    round(max_volume_threshold, ndigits=2)
    for max_volume_threshold in np.arange(2.25, 4.75, MAX_VOLUME_THRESHOLD_STEP_VALUE).tolist()
]
YES_NO_VALUES = ["Yes", "No"]
