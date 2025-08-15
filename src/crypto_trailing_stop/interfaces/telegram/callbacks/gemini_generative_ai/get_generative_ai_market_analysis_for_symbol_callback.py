import logging
import re
import time
from html import escape as html_escape

from aiogram import F, html
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.gemini_remote_service import GeminiRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.gemini_generative_ai_service import GeminiGenerativeAiService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
bit2me_remote_service = Bit2MeRemoteService()
crypto_analytics_service = CryptoAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    ccxt_remote_service=CcxtRemoteService(),
    buy_sell_signals_config_service=BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service),
)
gemini_generative_ai_service = GeminiGenerativeAiService(gemini_remote_service=GeminiRemoteService())

REGEX = r"^generate_generative_ai_content\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def get_generative_ai_market_analysis_for_symbol_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(REGEX, callback_query.data)
            symbol = match.group(1)
            tickers = await bit2me_remote_service.get_tickers_by_symbol(symbol)
            technical_indicators, *_ = await crypto_analytics_service.calculate_technical_indicators(symbol)
            formatted_metrics_list = []
            for over_candlestick in CandleStickEnum:
                current_crypto_metrics = await crypto_analytics_service.get_crypto_market_metrics(
                    symbol, over_candlestick=over_candlestick, technical_indicators=technical_indicators
                )
                current_crypto_metrics_formatted_message = messages_formatter.format_current_crypto_metrics_message(
                    over_candlestick, tickers, current_crypto_metrics
                )
                formatted_metrics_list.append(current_crypto_metrics_formatted_message)

            response = await gemini_generative_ai_service.get_generative_ai_market_analysis(
                symbol, formatted_metrics_list
            )
            title = html.bold(f"GENERATIVE AI MARKET ANALYSIS FOR {symbol}")
            full_title = f"🪄 {title} 🪄\n\n"
            sent_message = await callback_query.message.answer(f"{full_title}🧠 {html.italic('Thinking...')}")
            last_update_time = time.monotonic()
            streaming_message = full_title
            async for chunk in response:
                if chunk.text:
                    streaming_message += chunk.text
                current_time = time.monotonic()
                if current_time - last_update_time > 1.5:  # Update every 1.5 seconds
                    try:
                        await sent_message.edit_text(streaming_message + f"\n\n✍️ {html.italic('Typing...')}")
                        last_update_time = current_time
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e):
                            logger.debug(f"Error editing message: {e}")
                        else:
                            logger.warning(f"Unexpected error editing message: {str(e)}")
            await sent_message.edit_text(streaming_message)
        except Exception as e:
            logger.error(f"Error retrieving Generative AI market analysis: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ Error retrieving Generative AI market analysis. "
                + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to use Generative AI market analysis.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
