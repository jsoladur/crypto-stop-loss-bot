from typing import override
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService


class TrailingStopLostTaskService(AbstractTaskService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._scheduler: AsyncIOScheduler = get_scheduler()
        self._scheduler.add_job(
            func=self.run,
            trigger="interval",
            seconds=self._configuration_properties.job_interval_seconds,
        )

    @override
    async def run(self) -> None:
        raise NotImplementedError("Not implemented")
