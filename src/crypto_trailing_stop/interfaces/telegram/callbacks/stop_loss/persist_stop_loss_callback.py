import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem
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
stop_loss_percent_service = StopLossPercentService(
    bit2me_remote_service=bit2me_remote_service, global_flag_service=GlobalFlagService()
)
buy_sell_signals_config_service = BuySellSignalsConfigService(
    favourite_crypto_currency_service=FavouriteCryptoCurrencyService(bit2me_remote_service=Bit2MeRemoteService())
)
orders_analytics_service = OrdersAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    ccxt_remote_service=ccxt_remote_service,
    stop_loss_percent_service=stop_loss_percent_service,
    buy_sell_signals_config_service=buy_sell_signals_config_service,
    crypto_analytics_service=CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=ccxt_remote_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
    ),
)


@dp.callback_query(F.data.regexp(r"^persist_stop_loss\$\$(.+?)\$\$(.+)$"))
async def handle_persist_stop_loss_callback(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^persist_stop_loss\$\$(.+?)\$\$(.+)$", callback_query.data)
            symbol = match.group(1).strip().upper()
            percent_value = float(match.group(2).strip())
            await stop_loss_percent_service.save_or_update(StopLossPercentItem(symbol=symbol, value=percent_value))
            limit_sell_order_guard_metrics_list = (
                await orders_analytics_service.calculate_all_limit_sell_order_guard_metrics(symbol=symbol)
            )
            answer_text = messages_formatter.format_persist_stop_loss_message(
                symbol, percent_value, limit_sell_order_guard_metrics_list
            )
            await callback_query.message.answer(answer_text, reply_markup=keyboards_builder.get_home_keyboard())
        except Exception as e:
            logger.error(f"Error persisting stop loss: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while persisting a stop loss. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
