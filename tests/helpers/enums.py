from enum import Enum


class AutoEntryTraderWarningTypeEnum(str, Enum):
    NONE = "NONE"
    ATR_TOO_HIGH = "ATR_TOO_HIGH"
    NOT_ENOUGH_FUNDS = "NOT_ENOUGH_FUNDS"
