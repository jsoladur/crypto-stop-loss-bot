import logging
from abc import ABCMeta

from httpx import AsyncClient

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.tasks.base.abstract_task_service import AbstractTaskService

logger = logging.getLogger(__name__)


class AbstractTradingTaskService(AbstractTaskService, metaclass=ABCMeta):
    def __init__(self):
        super().__init__()
        self._bit2me_remote_service = Bit2MeRemoteService()

    async def _fetch_tickers_for_open_sell_orders(
        self, open_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> dict[str, Bit2MeTickersDto]:
        open_sell_order_symbols = set([open_sell_order.symbol for open_sell_order in open_sell_orders])
        ret = {
            symbol: await self._bit2me_remote_service.get_tickers_by_symbol(symbol, client=client)
            for symbol in open_sell_order_symbols
        }
        return ret
