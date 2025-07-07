from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd


@dataclass
class TechnicalIndicatorsCacheItem:
    technical_indicators: pd.DataFrame

    @property
    def next_update_datetime(self) -> datetime:
        current = self.technical_indicators.iloc[-1]  # Current candle
        expiration_datetime = current["timestamp"] + timedelta(hours=1)
        return expiration_datetime
