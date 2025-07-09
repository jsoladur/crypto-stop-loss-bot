from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum


@dataclass
class TechnicalIndicatorsCacheItem:
    technical_indicators: pd.DataFrame

    @property
    def next_update_datetime(self) -> datetime:
        current = self.technical_indicators.iloc[CandleStickEnum.CURRENT]  # Current candle
        expiration_datetime = current["timestamp"] + timedelta(hours=1)
        return expiration_datetime
