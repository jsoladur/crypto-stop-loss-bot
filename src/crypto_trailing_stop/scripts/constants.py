import numpy as np

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)

DEFAULT_TRADING_MARKET_CONFIG = SymbolMarketConfig(symbol="ANY/EUR", price_precision=4, amount_precision=6)
DEFAULT_LIMIT_DOWNLOAD_BATCHES = 1_000
MIN_ENTRIES_PER_WEEK = 0.75
DEFAULT_MONTHS_BACK = 13
OUT_OF_SAMPLE_MONTHS_BACK = 5
DECENT_WIN_RATE_THRESHOLD = 50.0
DEFAULT_MIN_PROFIT_FACTOR = 1.5
DEFAULT_MIN_SQN = 2.0
MIN_TRADES_FOR_DEFAULT_MONTHS_BACK = DEFAULT_MONTHS_BACK * (MIN_ENTRIES_PER_WEEK * 4)

MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION = 0.25
MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION = 0.5

MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION = [
    round(min_volume_threshold, ndigits=2)
    for min_volume_threshold in np.arange(0.5, 2.25, MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION).tolist()
]
MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION = [
    round(max_volume_threshold, ndigits=2)
    for max_volume_threshold in np.arange(2.5, 4, MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION).tolist()
]
ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS = 15
