from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from urllib.parse import urlunparse, urlencode, urlparse
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import (
    StopLossPercentItem,
)
import numpy as np


class KeyboardsBuilder:
    def __init__(self):
        self._configuration_properties = get_configuration_properties()

    def get_login_keyboard(self, state: FSMContext) -> InlineKeyboardMarkup:
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
                        "tgUserId": state.key.user_id,
                        "tgChatId": state.key.chat_id,
                        "tgBotId": state.key.bot_id,
                    }
                ),
                "",
            )
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="⎆ Login",
                url=auth_url,
            )
        )
        return builder.as_markup()

    def get_home_keyboard(self) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="📈 Get Global Summary", callback_data="get_global_summary"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🚏 Set Stop Loss Percent (%)",
                callback_data="set_stop_loss_percent",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⏻ Logout",
                callback_data="logout",
            )
        )
        return builder.as_markup()

    def get_stop_loss_percent_items_keyboard(
        self, stop_loss_percent_items: list[StopLossPercentItem]
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for stop_loss_percent_item in stop_loss_percent_items:
            builder.row(
                InlineKeyboardButton(
                    text=f"{stop_loss_percent_item.symbol} - {stop_loss_percent_item.value} %",
                    callback_data=f"set_stop_loss_percent$${stop_loss_percent_item.symbol}",
                )
            )
        return builder.as_markup()

    def get_stop_loss_percent_values_by_symbol_keyboard(
        self, symbol: str
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        buttons = [
            InlineKeyboardButton(
                text=f"{percent_value} %",
                callback_data=f"persist_stop_loss$${symbol}$${percent_value}",
            )
            for percent_value in np.arange(0.25, 5.25, 0.25).tolist()
        ]
        # Add buttons in rows of 3
        for i in range(0, len(buttons), 3):
            builder.row(*buttons[i : i + 3])
        builder.row(
            InlineKeyboardButton(
                text="<< Back",
                callback_data="set_stop_loss_percent",
            )
        )
        return builder.as_markup()
