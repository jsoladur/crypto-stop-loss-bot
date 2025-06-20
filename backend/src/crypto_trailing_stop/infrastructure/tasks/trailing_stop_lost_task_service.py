import logging
import math
import pydash
from typing import override
from httpx import AsyncClient
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    CreateNewBit2MeOrderDto,
)
from crypto_trailing_stop.commons.constants import (
    TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD,
    NUMBER_OF_DIGITS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)


logger = logging.getLogger(__name__)


class TrailingStopLostTaskService(AbstractTaskService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._trailing_stop_loss_percent = (
            self._configuration_properties.trailing_stop_loss_percent / 100
        )
        self._trailing_stop_loss_price_decrease_threshold = (
            1 - TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD
        )
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
        global_tickers_by_symbol: dict[str, Bit2MeTickersDto] = {}
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_sell_orders = (
                await self._bit2me_remote_service.get_pending_stop_limit_orders(
                    side="sell", client=client
                )
            )
            min_buy_order_amount_by_symbol = (
                await self._calculate_min_buy_order_amount_by_symbol(
                    opened_sell_orders, client=client
                )
            )
            for open_sell_order in opened_sell_orders:
                number_of_digits_in_price = NUMBER_OF_DIGITS_IN_PRICE_BY_SYMBOL.get(
                    open_sell_order.symbol,
                    2,
                )
                tickers_by_symbol = await self._get_or_fetch_get_tickers_by_symbol(
                    open_sell_order.symbol, global_tickers_by_symbol, client=client
                )
                # Stop price should be the minimum of the current price and the minimum buy order amount for that symbol
                stop_price_base = min(
                    tickers_by_symbol.close,
                    min_buy_order_amount_by_symbol[open_sell_order.symbol],
                )
                new_stop_price = round(
                    stop_price_base * (1 - self._trailing_stop_loss_percent),
                    ndigits=number_of_digits_in_price,
                )
                logger.info(
                    f"Supervising order {repr(open_sell_order)}: Looking for new stop price {new_stop_price}"
                )
                if open_sell_order.stop_price < new_stop_price:
                    logger.info(
                        f"Updating order {repr(open_sell_order)} to new stop price {new_stop_price} {open_sell_order.symbol}."
                    )
                    await self._bit2me_remote_service.cancel_order_by_id(
                        open_sell_order.id, client=client
                    )
                    new_order = await self._bit2me_remote_service.create_order(
                        order=CreateNewBit2MeOrderDto(
                            order_type=open_sell_order.order_type,
                            side=open_sell_order.side,
                            symbol=open_sell_order.symbol,
                            price=str(
                                round(
                                    new_stop_price
                                    * self._trailing_stop_loss_price_decrease_threshold,
                                    ndigits=number_of_digits_in_price,
                                )
                            ),
                            amount=str(open_sell_order.order_amount),
                            stop_price=str(new_stop_price),
                        ),
                        client=client,
                    )
                    logger.info(f"New Order has been created with id = {new_order.id}")
                else:
                    logger.info(
                        f"Order {repr(open_sell_order)} is still valid, no update needed."
                    )

    async def _calculate_min_buy_order_amount_by_symbol(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> dict[str, float]:
        open_sell_order_symbols = set(
            [open_sell_order.symbol for open_sell_order in opened_sell_orders]
        )
        opened_buy_orders = await self._bit2me_remote_service.get_pending_buy_orders(
            client=client
        )
        opened_buy_orders_by_symbol = pydash.group_by(
            opened_buy_orders, lambda order: order.symbol
        )
        min_buy_order_amount_by_symbol = {}
        for open_sell_order_symbol in open_sell_order_symbols:
            min_buy_order_amount = math.inf
            if open_sell_order_symbol in opened_buy_orders_by_symbol:
                min_buy_order_amount = pydash.min_by(
                    opened_buy_orders_by_symbol[open_sell_order_symbol],
                    lambda order: order.stop_price or order.price,
                )
            min_buy_order_amount_by_symbol[open_sell_order_symbol] = (
                min_buy_order_amount.stop_price or min_buy_order_amount.price
            )
        return min_buy_order_amount_by_symbol

    async def _get_or_fetch_get_tickers_by_symbol(
        self,
        symbol: str,
        global_tickers_by_symbol: dict[str, Bit2MeTickersDto] = {},
        *,
        client: AsyncClient,
    ) -> Bit2MeTickersDto:
        if symbol not in global_tickers_by_symbol:
            ret = global_tickers_by_symbol[
                symbol
            ] = await self._bit2me_remote_service.get_tickers_by_symbol(
                symbol, client=client
            )
        else:
            ret = global_tickers_by_symbol[symbol]
        return ret
