import logging
from html import escape as html_escape

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
bit2me_remote_service = Bit2MeRemoteService()
ccxt_remote_service = CcxtRemoteService()
buy_sell_signals_config_service = BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service)
orders_analytics_service = OrdersAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    ccxt_remote_service=ccxt_remote_service,
    stop_loss_percent_service=StopLossPercentService(
        bit2me_remote_service=bit2me_remote_service, global_flag_service=GlobalFlagService()
    ),
    buy_sell_signals_config_service=buy_sell_signals_config_service,
    crypto_analytics_service=CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=ccxt_remote_service,
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
            answer_text = messages_formatter.format_limit_sell_order_guard_metrics(limit_sell_order_guard_metrics_list)
            await callback_query.message.answer(answer_text)
        except Exception as e:
            logger.error(f"Error trying to get sell orders info: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while getting sell orders info. Please try again later:\n\n{html.code(html_escape(str(e)))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the sell orders info.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
