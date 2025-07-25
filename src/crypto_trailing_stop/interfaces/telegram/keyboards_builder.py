from urllib.parse import urlencode, urlparse, urlunparse

import pydash
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from crypto_trailing_stop.commons.constants import (
    AUTO_ENTRY_TRADER_CONFIG_STEPS_VALUE_LIST,
    SP_TP_PAIRS,
    STOP_LOSS_STEPS_VALUE_LIST,
)
from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.global_flag_item import GlobalFlagItem
from crypto_trailing_stop.infrastructure.services.vo.push_notification_item import PushNotificationItem
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem


class KeyboardsBuilder(metaclass=SingletonMeta):
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
                urlencode({"tgUserId": state.key.user_id, "tgChatId": state.key.chat_id, "tgBotId": state.key.bot_id}),
                "",
            )
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⎆ Login", url=auth_url))
        return builder.as_markup()

    def get_home_keyboard(self) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🪙 ₿alances", callback_data="get_pro_wallet_balances"))
        builder.row(
            InlineKeyboardButton(text="📈 Summary", callback_data="get_global_summary"),
            InlineKeyboardButton(text="📤 Sell Orders", callback_data="get_sell_orders_info"),
        )
        builder.row(
            InlineKeyboardButton(text="💵 Prices", callback_data="get_current_prices"),
            InlineKeyboardButton(text="🧮 Metrics", callback_data="current_metrics_home"),
        )
        builder.row(
            InlineKeyboardButton(text="⚡ Buy-Sell", callback_data="buy_sell_config_home"),
            InlineKeyboardButton(text="🧠 Auto-Entry", callback_data="auto_entry_trader_config_home"),
        )
        builder.row(
            InlineKeyboardButton(text="🕹️ Toggles", callback_data="global_flags_home"),
            InlineKeyboardButton(text="🔔 Alerts", callback_data="push_notificacions_home"),
        )
        builder.row(InlineKeyboardButton(text="🚏 Stop Loss %", callback_data="stop_loss_percent_home"))
        builder.row(InlineKeyboardButton(text="🚥 Market Signals", callback_data="last_market_signals_home"))
        builder.row(InlineKeyboardButton(text="📴 Logout", callback_data="logout"))
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
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_buy_sell_signals_config_keyboard(self, items: list[BuySellSignalsConfigItem]) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for item in items:
            builder.row(
                InlineKeyboardButton(
                    text=f"⚡ {item.symbol}", callback_data=f"set_buy_sell_signals_config$${item.symbol}"
                )
            )
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_auto_entry_trader_config_keyboard(self, items: list[AutoBuyTraderConfigItem]) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for item in items:
            builder.row(
                InlineKeyboardButton(
                    text=f"🧠 {item.symbol} • 💰 {item.fiat_wallet_percent_assigned}%",
                    callback_data=f"set_auto_entry_trader_config$${item.symbol}",
                )
            )
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_current_metrics_home_keyboard(self, crypto_currencies: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for crypto_currency in crypto_currencies:
            builder.row(
                InlineKeyboardButton(
                    text=f"🧮 {crypto_currency}", callback_data=f"get_current_metrics_for_symbol$${crypto_currency}"
                )
            )
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_stop_loss_percent_values_by_symbol_keyboard(self, symbol: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        buttons = [
            InlineKeyboardButton(
                text=f"{percent_value}%", callback_data=f"persist_stop_loss$${symbol}$${percent_value}"
            )
            for percent_value in STOP_LOSS_STEPS_VALUE_LIST
        ]
        # Add buttons in rows of 3
        for buttons_chunk in pydash.chunk(buttons, size=5):
            builder.row(*buttons_chunk)
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="stop_loss_percent_home"))
        return builder.as_markup()

    def get_auto_entry_trader_config_values_by_symbol_keyboard(self, symbol: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        buttons = [
            InlineKeyboardButton(
                text=f"💰 {percent_value}%",
                callback_data=f"persist_auto_entry_trader_config$${symbol}$${percent_value}",
            )
            for percent_value in AUTO_ENTRY_TRADER_CONFIG_STEPS_VALUE_LIST
        ]
        first_button, *remaining_buttons = buttons
        *buttons_for_chunk, last_button = remaining_buttons
        builder.row(first_button)
        for buttons_chunk in pydash.chunk(buttons_for_chunk, size=4):
            builder.row(*buttons_chunk)
        builder.row(last_button)
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="auto_entry_trader_config_home"))
        return builder.as_markup()

    def get_yes_no_keyboard(self, *, yes_button_callback_data: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="☑️ Yes", callback_data=yes_button_callback_data),
            InlineKeyboardButton(text="🔙 No", callback_data="go_back_home"),
        )
        return builder.as_markup()

    def get_push_notifications_home_keyboard(
        self, push_notification_items: list[PushNotificationItem]
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for item in push_notification_items:
            action_icon = "⏸️" if item.activated else "▶️"
            state_icon = "🔔" if item.activated else "🔕"
            builder.row(
                InlineKeyboardButton(
                    text=f"{state_icon} {action_icon} {item.notification_type.description}",
                    callback_data=f"toggle_push_notification$${item.notification_type.value}",
                )
            )
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_global_flags_home_keyboard(self, global_flags_items: list[GlobalFlagItem]) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for item in global_flags_items:
            action_icon = "⏸️" if item.value else "▶️"
            state_icon = "🟢" if item.value else "🟥"
            builder.row(
                InlineKeyboardButton(
                    text=f"{state_icon} {action_icon} {item.name.description}",
                    callback_data=f"toggle_global_flag$${item.name.value}",
                )
            )
        # Back button
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    def get_last_market_signals_symbols_keyboard(self, symbols: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for symbol in symbols:
            builder.row(InlineKeyboardButton(text=f"🚥 {symbol}", callback_data=f"show_last_market_signals$${symbol}"))
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="go_back_home"))
        return builder.as_markup()

    @staticmethod
    def get_sp_tp_pairs_keyboard() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        keyboard_buttons = [KeyboardButton(text=text) for text in SP_TP_PAIRS]
        for buttons_chunk in pydash.chunk(keyboard_buttons, size=2):
            builder.row(*buttons_chunk)
        return builder.as_markup()
