import logging
from typing import override
from httpx import AsyncClient
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.services import (
    StopLossPercentService,
    GlobalFlagService,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)


logger = logging.getLogger(__name__)


class LimitSellOrderGuardTaskService(AbstractTaskService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._stop_loss_percent_service = StopLossPercentService()
        self._global_flag_service = GlobalFlagService()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._scheduler: AsyncIOScheduler = get_scheduler()
        self._scheduler.add_job(
            func=self.run,
            trigger="interval",
            seconds=self._configuration_properties.job_interval_seconds,
            coalesce=True,
        )

    @override
    async def run(self) -> None:
        sell_limit_order_guard_enabled = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.SELL_LIMIT_ORDER_GUARD
        )
        if sell_limit_order_guard_enabled:
            await self._internal_run()
        else:
            logger.warning(
                "[ATTENTION] Trailing Stop Loss is DISABLED! This job will not apply any change over sell limit orders!"
            )

    async def _internal_run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_limit_sell_orders = (
                await self._bit2me_remote_service.get_pending_sell_orders(
                    order_type="limit", client=client
                )
            )
            if opened_limit_sell_orders:
                await self._handle_opened_limit_sell_orders(
                    opened_limit_sell_orders, client=client
                )
            else:
                logger.info(
                    "There are no opened limit sell orders to handle! Let's see in the upcoming executions..."
                )

    async def _handle_opened_stop_limit_sell_orders(
        self,
        opened_limit_sell_orders: list[Bit2MeOrderDto],
        *,
        client: AsyncClient,
    ) -> None:
        logger.info("Under construction!")
