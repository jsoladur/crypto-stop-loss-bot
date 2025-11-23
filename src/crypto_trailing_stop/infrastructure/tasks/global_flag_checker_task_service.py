import logging
from typing import override

from aiogram import html
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class GlobalFlagCheckerTaskService(AbstractTaskService):
    def __init__(
        self,
        configuration_properties: ConfigurationProperties,
        operating_exchange_service: AbstractOperatingExchangeService,
        push_notification_service: PushNotificationService,
        telegram_service: TelegramService,
        scheduler: AsyncIOScheduler,
        global_flag_service: GlobalFlagService,
    ):
        super().__init__(operating_exchange_service, push_notification_service, telegram_service, scheduler)
        self._configuration_properties = configuration_properties
        self._global_flag_service = global_flag_service
        self._job = self._create_job()

    @override
    async def start(self) -> None:
        """
        Start method does not do anything,
        this job will be running every time to collect buy/sell signals
        """

    @override
    async def stop(self) -> None:
        """
        Start method does not do anything,
        this job will be running every time to collect buy/sell signals
        """

    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum | None:
        return None

    @override
    async def _run(self) -> None:
        # Check if Limit Sell Order Guard Service is enabled!
        is_enabled_for_limit_sell_order_guard = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
        )
        sell_orders = await self._operating_exchange_service.get_pending_sell_orders()
        if sell_orders and not is_enabled_for_limit_sell_order_guard:
            title = f"🛑🛑 {html.bold('CRITICAL WARNING')} 🛑🛑"
            body = [
                f"{html.italic('Limit Sell Order Guard')} Job is {html.bold('OFF')}.",
                html.bold("Your positions are unprotected."),
                html.bold("TP/SL will not be triggered!)"),
                html.bold("Re-enable the guard ASAP!"),
            ]
            text_message = f"{title}\n\n{'\n'.join(body)}"
            await self._notify_alert_by_type(
                PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT, message=text_message
            )

    @override
    def _get_job_trigger(self) -> IntervalTrigger:
        return IntervalTrigger(seconds=self._configuration_properties.global_flag_checker_job_interval_seconds)
