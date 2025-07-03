import logging
from abc import ABC, abstractmethod

from aiogram import html
from apscheduler.job import Job
from apscheduler.triggers.base import BaseTrigger
from httpx import AsyncClient

from crypto_trailing_stop.config import get_configuration_properties, get_scheduler
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.services import TelegramService

logger = logging.getLogger(__name__)


class AbstractTaskService(ABC):
    def __init__(self) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._push_notification_service = PushNotificationService()
        self._telegram_service = TelegramService(
            session_storage_service=SessionStorageService(), keyboards_builder=KeyboardsBuilder()
        )
        self._job: Job | None = None

    async def start(self) -> None:
        if not self._job:
            self._job = self._create_job()
        else:  # pragma: no cover
            self._job.resume()

    async def stop(self) -> None:
        if self._job:
            self._job.pause()

    async def run(self) -> None:
        try:
            await self._run()
        except Exception as e:  # pragma: no cover
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    @abstractmethod
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        """
        Get the global flag type
        """

    @abstractmethod
    async def _run(self) -> None:
        """
        Run the task
        """

    @abstractmethod
    def _get_job_trigger(self) -> BaseTrigger:
        """
        Get the job trigger
        """

    def _create_job(self) -> Job:
        trigger = self._get_job_trigger()
        job = get_scheduler().add_job(
            id=self.__class__.__name__,
            func=self.run,
            trigger=trigger,
            max_instances=1,  # Prevent overlapping
            coalesce=True,  # Skip intermediate runs if one was missed
        )
        return job

    async def _fetch_tickers_by_simbols(
        self, symbols: list[str], *, client: AsyncClient
    ) -> dict[str, Bit2MeTickersDto]:
        ret = {
            symbol: await self._bit2me_remote_service.get_tickers_by_symbol(symbol, client=client) for symbol in symbols
        }
        return ret

    async def _notify_fatal_error_via_telegram(self, e: Exception) -> None:  # pragma: no cover
        try:
            telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BACKGROUND_JOB_FALTAL_ERRORS
            )
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(
                    chat_id=tg_chat_id,
                    text=f"⚠️ [{self.__class__.__name__}] FATAL ERROR occurred! "
                    + f"Please try again later:\n\n{html.code(str(e))}",
                )
        except Exception as e:
            logger.warning(f"Unexpected error, notifying fatal error via Telegram: {str(e)}", exc_info=True)
