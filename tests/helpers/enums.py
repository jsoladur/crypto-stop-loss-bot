from enum import Enum


class AutoEntryTraderWarningTypeEnum(str, Enum):
    NONE = "NONE"
    ATR_TOO_HIGH = "ATR_TOO_HIGH"
    NOT_ENOUGH_FUNDS = "NOT_ENOUGH_FUNDS"


class AutoEntryTraderUnexpectedErrorBuyMarketOrder(str, Enum):
    NONE = "NONE"
    NOT_ENOUGH_BALANCE = "NOT_ENOUGH_BALANCE"
    SUDDEN_CANCELLED_BUY_MARKET_ORDER = "SUDDEN_CANCELLED_BUY_MARKET_ORDER"
