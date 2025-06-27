import logging
from typing import override
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services import (
    GlobalFlagService,
)

logger = logging.getLogger(__name__)


class BuySellSignalsTaskService(AbstractTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._global_flag_service = GlobalFlagService()
        self._scheduler: AsyncIOScheduler = get_scheduler()
        self._scheduler.add_job(
            id=self.__class__.__name__,
            func=self.run,
            # FIXME: Production ready
            # trigger="cron",
            # minute=2,
            # hour="*",
            trigger="interval",
            seconds=5,
            coalesce=True,
        )

    @override
    async def run(self) -> None:
        is_buy_sell_signals_enabled = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.BUY_SELL_SIGNALS
        )
        if is_buy_sell_signals_enabled and (
            telegram_chat_ids
            := await self._push_notification_service.get_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT
            )
        ):
            await self._internal_run(telegram_chat_ids)
        else:
            logger.warning(
                "[ATTENTION] Buy/Sell Signals job is DISABLED! You will not receive any alert!!"
            )

    async def _internal_run(self, telegram_chat_ids: list[int]) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_crypto_currencies = (
                await self._bit2me_remote_service.get_favourite_crypto_currencies(
                    client=client
                )
            )
            bit2me_account_info = await self._bit2me_remote_service.get_account_info(
                client=client
            )
            symbols = [
                f"{crypto_currency}/{bit2me_account_info.profile.currency_code}"
                for crypto_currency in favourite_crypto_currencies
            ]
            for symbol in symbols:
                raise NotImplementedError("To be implemented!")
