import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
messages_formatter: MessagesFormatter = (
    application_container.interfaces_container().telegram_container().messages_formatter()
)
global_flag_service: GlobalFlagService = (
    application_container.infrastructure_container().services_container().global_flag_service()
)
orders_analytics_service: OrdersAnalyticsService = (
    application_container.infrastructure_container().services_container().orders_analytics_service()
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
