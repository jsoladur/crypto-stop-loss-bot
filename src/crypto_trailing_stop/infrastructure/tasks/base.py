from abc import ABC, abstractmethod
import logging
from httpx import AsyncClient
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.interfaces.telegram.services import TelegramService
from crypto_trailing_stop.infrastructure.services.push_notification_service import (
    PushNotificationService,
)
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import (
    StopLossPercentItem,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)
from aiogram import html

logger = logging.getLogger(__name__)


class AbstractTaskService(ABC):
    def __init__(self):
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._push_notification_service = PushNotificationService()
        self._telegram_service = TelegramService()

    @abstractmethod
    def run(self, *args, **kwargs) -> None:
        """
        Run the task
        """

    async def _find_stop_loss_percent_by_symbol(
        self, sell_order: Bit2MeOrderDto
    ) -> tuple[StopLossPercentItem, float]:
        crypto_currency_symbol = sell_order.symbol.split("/")[0].strip().upper()
        stop_loss_percent_item = (
            await self._stop_loss_percent_service.find_stop_loss_percent_by_symbol(
                symbol=crypto_currency_symbol
            )
        )
        stop_loss_percent_decimal_value = stop_loss_percent_item.value / 100
        logger.info(
            f"Stop Loss Percent for Symbol {crypto_currency_symbol} "
            + f"is setup to '{stop_loss_percent_item.value} %' (Decimal: {stop_loss_percent_decimal_value})..."
        )
        return stop_loss_percent_item, stop_loss_percent_decimal_value

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
