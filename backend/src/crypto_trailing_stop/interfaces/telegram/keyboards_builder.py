from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
        return builder.as_markup()

    def get_login_keyboard(self, message: Message) -> InlineKeyboardMarkup:
        """Builds the login keyboard with a button to log in."""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="Login",
                url=f"{self._configuration_properties.public_domain}/login/oauth?tg_user_id={message.from_user.id}",
            )
        )
        return builder.as_markup()
