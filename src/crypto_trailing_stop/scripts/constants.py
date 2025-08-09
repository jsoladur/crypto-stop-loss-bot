from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto

DEFAULT_TRADING_MARKET_CONFIG = Bit2MeMarketConfigDto.model_construct(price_precision=4, amount_precision=6)
DEFAULT_LIMIT_DOWNLOAD_BATCHES = 1_000
DEFAULT_BIT2ME_BASE_URL = "https://gateway.bit2me.com"
