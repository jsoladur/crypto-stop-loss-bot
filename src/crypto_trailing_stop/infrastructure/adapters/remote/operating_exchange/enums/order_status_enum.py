from enum import Enum


class OrderStatusEnum(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially-filled"
    CANCELLED = "cancelled"
    PARTIALLY_CANCELLED = "partially-cancelled"
    INACTIVE = "inactive"
