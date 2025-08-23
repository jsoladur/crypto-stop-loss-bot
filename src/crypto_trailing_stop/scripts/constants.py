from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto

DEFAULT_TRADING_MARKET_CONFIG = Bit2MeMarketConfigDto.model_construct(price_precision=4, amount_precision=6)
DEFAULT_LIMIT_DOWNLOAD_BATCHES = 1_000
MIN_TRADES_FOR_STATS = 15
DEFAULT_MONTHS_BACK = 6
MIN_ENTRIES_PER_WEEK = MIN_TRADES_FOR_STATS / (DEFAULT_MONTHS_BACK * 4)  # ~2 trades per week
DECENT_WIN_RATE_THRESHOLD = 60.0
