from enum import Enum


class OrderTypeEnum(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop-limit"
