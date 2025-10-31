import numpy as np

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)

DEFAULT_TRADING_MARKET_CONFIG = SymbolMarketConfig(symbol="ANY/EUR", price_precision=4, amount_precision=6)
DEFAULT_LIMIT_DOWNLOAD_BATCHES = 1_000
MIN_TRADES_FOR_STATS = 15
DEFAULT_MONTHS_BACK = 6
MIN_ENTRIES_PER_WEEK = MIN_TRADES_FOR_STATS / (DEFAULT_MONTHS_BACK * 4)  # ~2 trades per week
FIRST_ITERATION_DECENT_WIN_RATE_THRESHOLD = 60.0
SECOND_ITERATION_DECENT_WIN_RATE_THRESHOLD = 70.0


MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION = 0.25
MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION = 0.5

MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION = [
    round(min_volume_threshold, ndigits=2)
    for min_volume_threshold in np.arange(0.25, 2.25, MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION).tolist()
]
MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION = [
    round(max_volume_threshold, ndigits=2)
    for max_volume_threshold in np.arange(2.5, 4.5, MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION).tolist()
]
ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS = 15
