from abc import ABCMeta
import logging
from httpx import AsyncClient
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import (
    StopLossPercentService,
)

from crypto_trailing_stop.infrastructure.services.orders_analytics_service import (
    OrdersAnalyticsService,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)
from crypto_trailing_stop.infrastructure.services import (
    GlobalFlagService,
)
from crypto_trailing_stop.infrastructure.tasks.base.abstract_task_service import (
    AbstractTaskService,
)

logger = logging.getLogger(__name__)


class AbstractTradingTaskService(AbstractTaskService, metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        self._stop_loss_percent_service = StopLossPercentService(
            bit2me_remote_service=self._bit2me_remote_service,
            global_flag_service=GlobalFlagService(),
        )
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            stop_loss_percent_service=self._stop_loss_percent_service,
        )

    async def _fetch_tickers_for_open_sell_orders(
        self,
        open_sell_orders: list[Bit2MeOrderDto],
        *,
        client: AsyncClient,
    ) -> dict[str, Bit2MeTickersDto]:
        open_sell_order_symbols = set(
            [open_sell_order.symbol for open_sell_order in open_sell_orders]
        )
        ret = await self._fetch_tickers_by_simbols(
            open_sell_order_symbols, client=client
        )
        return ret
