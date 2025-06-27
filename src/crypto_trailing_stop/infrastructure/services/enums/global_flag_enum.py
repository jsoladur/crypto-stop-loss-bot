from enum import Enum
from typing import Any


class GlobalFlagTypeEnum(str, Enum):
    description: str

    TRAILING_STOP_LOSS = ("TRAILING_STOP_LOSS", "Trailing Stop Loss")
    LIMIT_SELL_ORDER_GUARD = ("LIMIT_SELL_ORDER_GUARD", "Limit Sell Order Guard")
    BUY_SELL_SIGNALS = ("BUY_SELL_SIGNALS", "Buy/Sell Signals")

    @classmethod
    def from_value(cls, value: str) -> "GlobalFlagTypeEnum":
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"{value!r} is not a valid {cls.__name__}")

    def __new__(cls, value: str, description: str) -> "GlobalFlagTypeEnum":
        obj: Any = str.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj
