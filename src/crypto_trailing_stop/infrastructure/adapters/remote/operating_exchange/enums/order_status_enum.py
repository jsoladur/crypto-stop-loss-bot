from enum import Enum


class OrderStatusEnum(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    INACTIVE = "inactive"
