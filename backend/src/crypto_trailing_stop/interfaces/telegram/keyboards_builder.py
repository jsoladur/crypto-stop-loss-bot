from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from urllib.parse import urlunparse, urlencode, urlparse
from crypto_trailing_stop.config import get_configuration_properties


class KeyboardsBuilder:
    def __init__(self):
        self._configuration_properties = get_configuration_properties()

    def get_home_keyboard(self) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="Get Global Summary", callback_data="get_global_summary"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Set Stop Loss Percentage (%)",
                callback_data="set_stop_loss_percentage",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Logout",
                callback_data="logout",
            )
        )
        return builder.as_markup()

    def get_login_keyboard(self, message: Message) -> InlineKeyboardMarkup:
        """Builds the login keyboard with a button to log in."""
        # Base components
        parsed_public_domain = urlparse(self._configuration_properties.public_domain)
        # Build full URL
        auth_url = urlunparse(
            (
                parsed_public_domain.scheme,
                parsed_public_domain.netloc,
                "/login/oauth",
                "",
                urlencode(
                    {
                        "tgUserId": message.from_user.id,
                        "tgChatId": message.chat.id,
                        "tgUsername": message.from_user.username,
                    }
                ),
                "",
            )
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="Login",
                url=auth_url,
            )
        )
        return builder.as_markup()
