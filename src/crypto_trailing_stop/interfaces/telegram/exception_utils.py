from html import escape

import pydash

from crypto_trailing_stop.commons.constants import TELEGRAM_REPLY_EXCEPTION_MESSAGE_MAX_LENGTH


def format_exception(e: Exception) -> str:
    exception_message = str(e)
    exception_message = exception_message if exception_message is not None else ""
    if exception_message:
        exception_message = escape(exception_message)
        exception_message = pydash.truncate(str(e), length=TELEGRAM_REPLY_EXCEPTION_MESSAGE_MAX_LENGTH)

    return exception_message
