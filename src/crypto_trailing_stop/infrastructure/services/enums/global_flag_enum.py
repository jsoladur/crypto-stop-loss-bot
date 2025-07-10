from enum import Enum
from typing import Any


class GlobalFlagTypeEnum(str, Enum):
    description: str

    TRAILING_STOP_LOSS = ("TRAILING_STOP_LOSS", "Trailing Stop Loss")
    LIMIT_SELL_ORDER_GUARD = ("LIMIT_SELL_ORDER_GUARD", "Limit Sell Guard")
    AUTO_EXIT_SELL_1H = ("AUTO_EXIT_SELL_1H", "Auto SELL 1H Exit")
    AUTO_EXIT_ATR_TAKE_PROFIT = ("AUTO_EXIT_ATR_TAKE_PROFIT", "Auto ATR Take-Profit Exit")
    BUY_SELL_SIGNALS = ("BUY_SELL_SIGNALS", "Buy/Sell Signals")
    AUTO_ENTRY_TRADER = ("AUTO_ENTRY_TRADER", "Auto-Entry Trader")

    @classmethod
    def from_value(cls, value: str) -> "GlobalFlagTypeEnum":
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"{value!r} is not a valid {cls.__name__}")  # pragma: no cover

    def __new__(cls, value: str, description: str) -> "GlobalFlagTypeEnum":
        obj: Any = str.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj
