import numpy as np

DEFAULT_JOB_INTERVAL_SECONDS = 5  # 5 seconds
DEFAULT_TRAILING_STOP_LOSS_PERCENT = 5.0  # Best Spot Loss value intra-day, based on experience
STOP_LOSS_STEPS_VALUE_LIST = np.concatenate(
    (np.arange(0.25, 5.25, 0.25), np.arange(5.50, 10.50, 0.50), np.arange(11, 21, 1))
).tolist()
TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD = 0.00025
NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL = {"BTC/EUR": 1, "SUI/EUR": 4, "XRP/EUR": 4}
DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE = 2
NUMBER_OF_DECIMALS_IN_QUANTITY_BY_SYMBOL = {"BTC/EUR": 8, "ETH/EUR": 8, "SUI/EUR": 5, "XRP/EUR": 6}
DEFAULT_NUMBER_OF_DECIMALS_IN_QUANTITY = 4
DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS = 86_400  # 1 day
# Removing number of executions
BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN = [0, 1, 2, 3, 5, 15, 30, 31, 32, 33, 35, 45]
BUY_SELL_RELIABLE_TIMEFRAMES = ["4h", "1h"]
ANTICIPATION_ZONE_TIMEFRAMES = ["30m"]
# Event Emitter - Event names
SIGNALS_EVALUATION_RESULT_EVENT_NAME = "signals_evaluation_result"
TRIGGER_BUY_ACTION_EVENT_NAME = "trigger_buy_action"
# Bit2Me Fees
BIT2ME_MAKER_FEES = 0.00159
BIT2ME_TAKER_FEES = 0.00259
BIT2ME_MAKER_AND_TAKER_FEES_SUM = BIT2ME_MAKER_FEES + BIT2ME_TAKER_FEES
# Auto-Entry Trader
AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST = 25.0
AUTO_ENTRY_TRADER_CONFIG_STEPS_VALUE_LIST = np.arange(0, 105, 5).tolist()
# Buy Sell Signals Config
EMA_SHORT_MID_PAIRS = [f"{ema_short}/{ema_mid}" for ema_short, ema_mid in [(7, 18), (8, 20), (9, 21)]]
SP_TP_PAIRS = [
    f"{sp_percent}/{tp_percent}"
    for sp_percent, tp_percent in [
        (2.5, 3.5),  # RRR: 1.4
        (2.5, 3.8),  # RRR: 1.52
        (2.5, 4.0),  # RRR: 1.6
        (2.5, 4.2),  # RRR: 1.68
        (3.0, 4.2),  # RRR: 1.4
        (3.0, 4.5),  # RRR: 1.5
        (3.0, 4.8),  # RRR: 1.6
        (3.0, 5.1),  # RRR: 1.7
    ]
]
EMA_LONG_VALUES = [150, 200, 233]
ADX_THRESHOLD_VALUES = [15, 20, 25]
YES_NO_VALUES = ["Yes", "No"]
