from enum import Enum
from typing import Any


class PushNotificationTypeEnum(str, Enum):
    description: str

    BUY_SELL_STRATEGY_ALERT = ("BUY_SELL_STRATEGY_ALERT", "Buy/Sell Strategy alerts")
    LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT = (
        "LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT",
        "Limit Sell Order Guard alerts",
    )
    BACKGROUND_JOB_FALTAL_ERRORS = (
        "BACKGROUND_JOB_FALTAL_ERRORS",
        "Jobs Fatal Errors alerts",
    )

    @classmethod
    def from_value(cls, value: str) -> "PushNotificationTypeEnum":
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"{value!r} is not a valid {cls.__name__}")

    def __new__(cls, value: str, description: str) -> "PushNotificationTypeEnum":
        obj: Any = str.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj
