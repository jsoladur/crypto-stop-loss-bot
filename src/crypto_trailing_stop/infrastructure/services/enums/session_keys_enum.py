from enum import Enum


class SessionKeysEnum(str, Enum):
    """
    Enum for session keys used in the application.
    """

    USER_CONTEXT = "user_ctx"
    BUY_SELL_SIGNALS_SYMBOL_FORM = "buy_sell_signals_symbol_form"
