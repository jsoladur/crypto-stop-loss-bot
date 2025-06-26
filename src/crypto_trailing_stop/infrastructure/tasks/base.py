from abc import ABC, abstractmethod
import logging
from httpx import AsyncClient
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.interfaces.telegram.services import TelegramService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import (
    StopLossPercentService,
)
from crypto_trailing_stop.infrastructure.services.push_notification_service import (
    PushNotificationService,
)
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import (
    OrdersAnalyticsService,
)
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from aiogram import html

logger = logging.getLogger(__name__)


class AbstractTaskService(ABC):
    def __init__(self):
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._push_notification_service = PushNotificationService()
        self._stop_loss_percent_service = StopLossPercentService(
            bit2me_remote_service=self._bit2me_remote_service
        )
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            stop_loss_percent_service=self._stop_loss_percent_service,
        )
        self._telegram_service = TelegramService(
            session_storage_service=SessionStorageService(),
            keyboards_builder=KeyboardsBuilder(),
        )

    @abstractmethod
    async def run(self, *args, **kwargs) -> None:
        """
        Run the task
        """

    async def _fetch_all_tickers_by_symbol(
        self,
        opened_stop_limit_sell_orders: list[Bit2MeOrderDto],
        *,
        client: AsyncClient,
    ) -> dict[str, Bit2MeTickersDto]:
        open_sell_order_symbols = set(
            [
                open_sell_order.symbol
                for open_sell_order in opened_stop_limit_sell_orders
            ]
        )
        ret = {
            symbol: await self._bit2me_remote_service.get_tickers_by_symbol(
                symbol, client=client
            )
            for symbol in open_sell_order_symbols
        }
        return ret

    async def _notify_fatal_error_via_telegram(self, e: Exception) -> None:
        try:
            telegram_chat_ids = await self._push_notification_service.get_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BACKGROUND_JOB_FALTAL_ERRORS
            )
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(
                    chat_id=tg_chat_id,
                    text=f"⚠️ [{self.__class__.__name__}] FATAL ERROR occurred! Please try again later:\n\n{html.code(str(e))}",
                )
        except Exception as e:
            logger.warning(
                f"Unexpected error, notifying fatal error via Telegram: {str(e)}",
                exc_info=True,
            )
