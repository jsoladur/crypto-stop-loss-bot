import logging
import re

from aiogram import Bot, Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.callbacks.buy_sell_signals_config.buy_sell_signals_config_form import (
    BuySellSignalsConfigForm,
)
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
configuration_properties: ConfigurationProperties = application_container.configuration_properties()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
bot: Bot = application_container.interfaces_container().telegram_container().telegram_bot()
messages_formatter: MessagesFormatter = (
    application_container.interfaces_container().telegram_container().messages_formatter()
)
buy_sell_signals_config_service: BuySellSignalsConfigService = (
    application_container.infrastructure_container().services_container().buy_sell_signals_config_service()
)


@BuySellSignalsConfigForm.submit(router=dp)
async def buy_sell_signals_config_form_submit_handler(form: BuySellSignalsConfigForm):
    try:
        symbol = await session_storage_service.get_buy_sell_signals_symbol_form(form.chat_id)
        item = form.to_persistable(symbol, configuration_properties=configuration_properties)
        await buy_sell_signals_config_service.save_or_update(item)
        message = f"✅ Buy/Sell signals for {html.bold(symbol)} configuration successfully persisted.\n\n"
        message += messages_formatter.format_buy_sell_signals_config_message(item)
        await form.answer(message, reply_markup=keyboards_builder.get_home_keyboard())
    except Exception as e:
        logger.error(f"Error persisting Buy/Sell signals config: {str(e)}", exc_info=True)
        await form.answer(
            "⚠️ An error occurred while persisting an Buy/Sell signals configuration. "
            + f"Please try again later:\n\n{html.code(format_exception(e))}"
        )


@dp.callback_query(F.data.regexp(r"^persist_buy_sell_signals_config\$\$(.+)$"))
async def persist_buy_sell_signals_config_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^persist_buy_sell_signals_config\$\$(.+)$", callback_query.data)
            symbol = match.group(1).strip().upper()
            await session_storage_service.set_buy_sell_signals_symbol_form(state, symbol)
            await BuySellSignalsConfigForm.start(bot, state)
        except Exception as e:
            logger.error(f"Error persisting Buy/Sell signals config: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while persisting an Buy/Sell signals configuration. "
                + f"Please try again later:\n\n{html.code(format_exception(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the corresponding Buy/Sell signals configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
