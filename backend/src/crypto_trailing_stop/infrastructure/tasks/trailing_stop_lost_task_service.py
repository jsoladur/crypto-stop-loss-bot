import logging
from typing import override
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService

logger = logging.getLogger(__name__)


class TrailingStopLostTaskService(AbstractTaskService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._scheduler: AsyncIOScheduler = get_scheduler()
        self._scheduler.add_job(
            func=self.run,
            trigger="interval",
            seconds=self._configuration_properties.job_interval_seconds,
        )

    @override
    async def run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_sell_orders = await self._bit2me_remote_service.get_sell_orders(
                client=client
            )
            for open_sell_order in opened_sell_orders:
                logger.info(f"open_sell_order: {open_sell_order}")
