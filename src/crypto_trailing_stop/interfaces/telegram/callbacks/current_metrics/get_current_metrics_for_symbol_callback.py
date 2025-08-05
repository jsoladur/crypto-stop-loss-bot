import logging
import re
from html import escape as html_escape

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
bit2me_remote_service = Bit2MeRemoteService()
global_flag_service = GlobalFlagService()
auto_buy_trader_config_service = AutoBuyTraderConfigService(bit2me_remote_service=bit2me_remote_service)
crypto_analytics_service = CryptoAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    ccxt_remote_service=CcxtRemoteService(),
    buy_sell_signals_config_service=BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service),
)


@dp.callback_query(F.data.regexp(r"^get_current_metrics_for_symbol\$\$(.+)$"))
async def auto_entry_trader_config_for_symbol_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^get_current_metrics_for_symbol\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            over_candlestick = CandleStickEnum.LAST
            tickers = await bit2me_remote_service.get_tickers_by_symbol(symbol)
            current_crypto_metrics = await crypto_analytics_service.get_crypto_market_metrics(
                symbol, over_candlestick=over_candlestick
            )
            message = messages_formatter.format_current_crypto_metrics_message(
                over_candlestick, tickers, current_crypto_metrics
            )
            message += "\n\n"
            is_enabled_for_auto_entry_trader = await global_flag_service.is_enabled_for(
                GlobalFlagTypeEnum.AUTO_ENTRY_TRADER
            )
            crypto_currency, *_ = symbol.split("/")
            auto_buy_trader_config = await auto_buy_trader_config_service.find_by_symbol(crypto_currency)
            if is_enabled_for_auto_entry_trader and auto_buy_trader_config.fiat_wallet_percent_assigned > 0:
                message += (
                    "ℹ️️ Would you like to trigger a buy trade operation via Auto-Entry Trader manually, "
                    + "given the current market situation?"
                )
                inline_keyboard_markup = keyboards_builder.get_yes_no_keyboard(
                    yes_button_callback_data=f"auto_entry_trader_manual_trigger_confirmation$${symbol}"
                )
            else:
                message += f"💡 {html.italic('Enable Auto-Entry Trader and assign capital to ' + symbol + ' to allow manual buys.')}"  # noqa: E501
                inline_keyboard_markup = keyboards_builder.get_go_back_home_keyboard()
            await callback_query.message.answer(message, reply_markup=inline_keyboard_markup)
        except Exception as e:
            logger.error(f"Error retrieving current crypto metrics: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving current crypto metrics for {symbol}. "
                + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get current crypto metrics for any symbol.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
