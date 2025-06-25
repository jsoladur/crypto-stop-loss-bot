from enum import Enum


class SessionKeysEnum(str, Enum):
    """
    Enum for session keys used in the application.
    """

    USER_CONTEXT = "user_ctx"
