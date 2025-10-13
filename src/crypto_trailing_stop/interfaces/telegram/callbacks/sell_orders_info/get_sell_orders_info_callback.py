import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
bit2me_remote_service = Bit2MeRemoteService()
ccxt_remote_service = CcxtRemoteService()
global_flag_service = GlobalFlagService()
favourite_crypto_currency_service = FavouriteCryptoCurrencyService(bit2me_remote_service=Bit2MeRemoteService())
buy_sell_signals_config_service = BuySellSignalsConfigService(
    favourite_crypto_currency_service=favourite_crypto_currency_service
)
orders_analytics_service = OrdersAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    ccxt_remote_service=ccxt_remote_service,
    stop_loss_percent_service=StopLossPercentService(
        favourite_crypto_currency_service=favourite_crypto_currency_service, global_flag_service=GlobalFlagService()
    ),
    buy_sell_signals_config_service=buy_sell_signals_config_service,
    crypto_analytics_service=CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=ccxt_remote_service,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
    ),
)


@dp.callback_query(lambda c: c.data == "get_sell_orders_info")
async def get_sell_orders_info_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            limit_sell_order_guard_metrics_list = (
                await orders_analytics_service.calculate_all_limit_sell_order_guard_metrics()
            )
            if limit_sell_order_guard_metrics_list:
                is_enabled_for_limit_sell_order_guard = await global_flag_service.is_enabled_for(
                    GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
                )
                for idx, metrics in enumerate(limit_sell_order_guard_metrics_list):
                    answer_text = messages_formatter.format_limit_sell_order_guard_metrics(metrics)
                    answer_text += "\n"
                    if is_enabled_for_limit_sell_order_guard:
                        answer_text += (
                            "ℹ️️ Would you like to immediate sell this operation via Limit Sell Guard manually?"
                        )
                        inline_keyboard_markup = keyboards_builder.get_yes_no_keyboard(
                            yes_button_callback_data=f"choose_sell_percent$${metrics.sell_order.id}"
                        )
                    else:
                        answer_text += f"💡 {html.italic('The Limit Sell Order Guard is currently disabled. Please enable it if you want to immediate sell this operation')}"  # noqa: E501
                        inline_keyboard_markup = None
                        if idx + 1 >= len(limit_sell_order_guard_metrics_list):
                            inline_keyboard_markup = keyboards_builder.get_go_back_home_keyboard()
                    await callback_query.message.answer(answer_text, reply_markup=inline_keyboard_markup)
            else:
                await callback_query.message.answer("✳️ There are no currently opened SELL orders.")
        except Exception as e:
            logger.error(f"Error trying to get sell orders info: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while getting sell orders info. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the sell orders info.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
