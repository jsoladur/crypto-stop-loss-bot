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
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import (
    StopLossPercentItem,
)
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    CreateNewBit2MeOrderDto,
)
from crypto_trailing_stop.commons.constants import (
    TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
)
from crypto_trailing_stop.infrastructure.services import (
    StopLossPercentService,
    GlobalFlagService,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)


logger = logging.getLogger(__name__)


class TrailingStopLossTaskService(AbstractTaskService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._stop_loss_percent_service = StopLossPercentService()
        self._global_flag_service = GlobalFlagService()
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
        is_trailing_stop_loss_enabled = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.TRAILING_STOP_LOSS
        )
        if is_trailing_stop_loss_enabled:
            await self._internal_run()
        else:
            logger.warning(
                "[ATTENTION] Stop Loss is disabled! This job will not apply any change over opened sell orders!"
            )

    async def _internal_run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_sell_orders = (
                await self._bit2me_remote_service.get_pending_stop_limit_orders(
                    side="sell", client=client
                )
            )
            if opened_sell_orders:
                await self._handle_opened_sell_orders(opened_sell_orders, client=client)
            else:
                logger.info(
                    "There are no opened sell orders to handle! Let's see in the upcoming executions..."
                )

    async def _handle_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> None:
        current_tickers_by_symbol: dict[
            str, Bit2MeTickersDto
        ] = await self._fetch_all_tickers_by_symbol(opened_sell_orders, client=client)
        max_and_min_buy_order_amount_by_symbol = (
            await self._calculate_max_and_min_buy_order_amount_by_symbol(
                opened_sell_orders, current_tickers_by_symbol, client=client
            )
        )
        for open_sell_order in opened_sell_orders:
            number_of_digits_in_price = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                open_sell_order.symbol,
                DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
            )
            crypto_currency_symbol = (
                open_sell_order.symbol.split("/")[0].strip().upper()
            )
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
            # Stop price should be the minimum of the current price and the minimum buy order amount for that symbol
            max_buy_order_amount, min_buy_order_amount = (
                max_and_min_buy_order_amount_by_symbol[open_sell_order.symbol]
            )
            tickers = current_tickers_by_symbol[open_sell_order.symbol]
            stop_price_base = self._calculate_stop_price_base(
                current_symbol_price=tickers.close,
                max_buy_order_amount=max_buy_order_amount,
                min_buy_order_amount=min_buy_order_amount,
                stop_loss_percent_item=stop_loss_percent_item,
            )
            new_stop_price = round(
                stop_price_base * (1 - stop_loss_percent_decimal_value),
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

    def _calculate_stop_price_base(
        self,
        *,
        current_symbol_price: float | int,
        max_buy_order_amount: float | int,
        min_buy_order_amount: float | int,
        stop_loss_percent_item: StopLossPercentItem,
    ):
        # XXX: [JMSOLA] Even though there could be a buy order, if the difference between
        #      the current price and the max_buy_order_amount is greater than the corresponding Stop Loss Percent value,
        #      then we will calculate new stop loss price based on the current price in order to maximise gains
        if max_buy_order_amount == math.inf or (
            current_symbol_price > max_buy_order_amount
            and ((1 - (max_buy_order_amount / current_symbol_price)) * 100)
            > stop_loss_percent_item.value
        ):
            stop_price_base = current_symbol_price
        else:
            stop_price_base = min(
                current_symbol_price,
                min_buy_order_amount,
            )
        return stop_price_base

    async def _calculate_max_and_min_buy_order_amount_by_symbol(
        self,
        opened_sell_orders: list[Bit2MeOrderDto],
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        *,
        client: AsyncClient,
    ) -> dict[str, tuple[float, float]]:
        open_sell_order_symbols = set(
            [open_sell_order.symbol for open_sell_order in opened_sell_orders]
        )
        opened_buy_orders = await self._bit2me_remote_service.get_pending_buy_orders(
            client=client
        )
        # XXX: Discard all buy orders that have higher price than the current corresponding symbol one
        opened_buy_orders = [
            order
            for order in opened_buy_orders
            if order.effective_price < current_tickers_by_symbol[order.symbol].close
        ]
        opened_buy_orders_by_symbol = pydash.group_by(
            opened_buy_orders, lambda order: order.symbol
        )
        max_and_min_buy_order_amount_by_symbol = {}
        for open_sell_order_symbol in open_sell_order_symbols:
            if (
                open_sell_order_symbol in opened_buy_orders_by_symbol
                and opened_buy_orders_by_symbol[open_sell_order_symbol]
            ):
                max_buy_order = pydash.max_by(
                    opened_buy_orders_by_symbol[open_sell_order_symbol],
                    lambda order: order.effective_price,
                )
                min_buy_order = pydash.min_by(
                    opened_buy_orders_by_symbol[open_sell_order_symbol],
                    lambda order: order.effective_price,
                )
                max_and_min_buy_order_amount_by_symbol[open_sell_order_symbol] = (
                    max_buy_order.effective_price,
                    min_buy_order.effective_price,
                )
            else:
                max_and_min_buy_order_amount_by_symbol[open_sell_order_symbol] = (
                    math.inf,
                    math.inf,
                )

        return max_and_min_buy_order_amount_by_symbol

    async def _fetch_all_tickers_by_symbol(
        self,
        opened_sell_orders: list[Bit2MeOrderDto],
        *,
        client: AsyncClient,
    ) -> dict[str, Bit2MeTickersDto]:
        open_sell_order_symbols = set(
            [open_sell_order.symbol for open_sell_order in opened_sell_orders]
        )
        ret = {
            symbol: await self._bit2me_remote_service.get_tickers_by_symbol(
                symbol, client=client
            )
            for symbol in open_sell_order_symbols
        }
        return ret
