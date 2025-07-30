from enum import Enum


class CandleStickEnum(int, Enum):
    CURRENT = -1  # Current uncompleted candle
    LAST = -2  # Last confirmed candle
    PREV = -3  # Prev confirmed candle
    PRIOR = -4  # Prior confirmed candle
    OLDEST = -5  # Oldest confirmed candle
