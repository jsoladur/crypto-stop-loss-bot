import logging
import math
from abc import ABC
from html import escape as html_escape

from aiogram import html
from httpx import AsyncClient

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class AbstractService(ABC):
    def __init__(self) -> None:
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._push_notification_service = PushNotificationService()
        self._telegram_service = TelegramService(
            session_storage_service=SessionStorageService(), keyboards_builder=KeyboardsBuilder()
        )

    async def _fetch_tickers_for_open_sell_orders(
        self, open_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> dict[str, Bit2MeTickersDto]:
        open_sell_order_symbols = set([open_sell_order.symbol for open_sell_order in open_sell_orders])
        tickers_list = await self._bit2me_remote_service.get_tickers_by_symbols(
            symbols=open_sell_order_symbols, client=client
        )
        ret = {tickers.symbol: tickers for tickers in tickers_list}
        return ret

    async def _get_last_buy_trades_by_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> dict[str, list[Bit2MeTradeDto]]:
        opened_sell_order_symbols = set([sell_order.symbol for sell_order in opened_sell_orders])
        last_buy_trades_by_symbol = {
            symbol: await self._bit2me_remote_service.get_trades(side="buy", symbol=symbol, client=client)
            for symbol in opened_sell_order_symbols
        }
        return last_buy_trades_by_symbol

    async def _notify_alert_by_type(self, notification_type: PushNotificationTypeEnum, message: str) -> None:
        telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
            notification_type=notification_type
        )
        for tg_chat_id in telegram_chat_ids:
            await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)

    async def _notify_fatal_error_via_telegram(self, e: Exception) -> None:
        exception_text = f"{e.__class__.__name__} :: {str(e)}" if str(e) else e.__class__.__name__
        try:
            telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BACKGROUND_JOB_FALTAL_ERRORS
            )
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(
                    chat_id=tg_chat_id,
                    text=f"⚠️ [{self.__class__.__name__}] FATAL ERROR occurred! "
                    + f"Please try again later:\n\n{html.code(html_escape(exception_text))}",
                )
        except Exception as e:
            logger.warning(f"Unexpected error, notifying fatal error via Telegram: {exception_text}", exc_info=True)

    def _floor_round(self, value: float, *, ndigits: int) -> float:
        factor = 10**ndigits
        return math.floor(value * factor) / factor
