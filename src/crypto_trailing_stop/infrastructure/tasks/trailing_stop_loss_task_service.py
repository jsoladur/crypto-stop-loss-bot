import logging
import math
from typing import override

import pydash
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD,
)
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTradingTaskService

logger = logging.getLogger(__name__)


class TrailingStopLossTaskService(AbstractTradingTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._orders_analytics_service = OrdersAnalyticsService()
        self._trailing_stop_loss_price_decrease_threshold = 1 - TRAILING_STOP_LOSS_PRICE_DECREASE_THRESHOLD

    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.TRAILING_STOP_LOSS

    @override
    async def _run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_stop_limit_sell_orders = await self._bit2me_remote_service.get_pending_sell_orders(
                order_type="stop-limit", client=client
            )
            if opened_stop_limit_sell_orders:
                await self._handle_opened_stop_limit_sell_orders(opened_stop_limit_sell_orders, client=client)
            else:
                logger.info(
                    "There are no opened stop-limit sell orders to handle! Let's see in the upcoming executions..."
                )

    @override
    def _get_job_trigger(self) -> IntervalTrigger:
        return IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)

    async def _handle_opened_stop_limit_sell_orders(
        self, opened_stop_limit_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> None:
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = await self._fetch_tickers_for_open_sell_orders(
            opened_stop_limit_sell_orders, client=client
        )
        max_and_min_buy_order_amount_by_symbol = await self._calculate_max_and_min_buy_order_amount_by_symbol(
            opened_stop_limit_sell_orders, current_tickers_by_symbol, client=client
        )
        for sell_order in opened_stop_limit_sell_orders:
            try:
                await self._handle_single_sell_order(
                    sell_order, current_tickers_by_symbol, max_and_min_buy_order_amount_by_symbol, client=client
                )
            except Exception as e:  # pragma: no cover
                logger.error(str(e), exc_info=True)
                await self._notify_fatal_error_via_telegram(e)

    async def _handle_single_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        max_and_min_buy_order_amount_by_symbol: dict[str, tuple[float, float]],
        *,
        client: AsyncClient,
    ) -> None:
        number_of_digits_in_price = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
            sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
        )
        (
            stop_loss_percent_item,
            stop_loss_percent_decimal_value,
        ) = await self._orders_analytics_service.find_stop_loss_percent_by_sell_order(sell_order)
        # Stop price should be the minimum of the current price and the minimum buy order amount for that symbol
        max_buy_order_amount, min_buy_order_amount = max_and_min_buy_order_amount_by_symbol[sell_order.symbol]
        tickers = current_tickers_by_symbol[sell_order.symbol]
        stop_price_base = self._calculate_stop_price_base(
            current_symbol_price=tickers.close,
            max_buy_order_amount=max_buy_order_amount,
            min_buy_order_amount=min_buy_order_amount,
            stop_loss_percent_item=stop_loss_percent_item,
        )
        new_stop_price = round(
            stop_price_base * (1 - stop_loss_percent_decimal_value), ndigits=number_of_digits_in_price
        )
        logger.info(
            f"Supervising STOP-LIMIT SELL order {repr(sell_order)}: Looking for new stop price {new_stop_price}"
        )
        if sell_order.stop_price < new_stop_price:
            logger.info(f"Updating order {repr(sell_order)} to new stop price {new_stop_price} {sell_order.symbol}.")
            await self._bit2me_remote_service.cancel_order_by_id(sell_order.id, client=client)
            new_order = await self._bit2me_remote_service.create_order(
                order=CreateNewBit2MeOrderDto(
                    order_type=sell_order.order_type,
                    side=sell_order.side,
                    symbol=sell_order.symbol,
                    price=str(
                        round(
                            new_stop_price * self._trailing_stop_loss_price_decrease_threshold,
                            ndigits=number_of_digits_in_price,
                        )
                    ),
                    amount=str(sell_order.order_amount),
                    stop_price=str(new_stop_price),
                ),
                client=client,
            )
            logger.info(f"New Order has been created with id = {new_order.id}")
        else:
            logger.info(f"Order {repr(sell_order)} is still valid, no update needed.")

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
            and ((1 - (max_buy_order_amount / current_symbol_price)) * 100) > stop_loss_percent_item.value
        ):
            stop_price_base = current_symbol_price
        else:
            stop_price_base = min(current_symbol_price, min_buy_order_amount)
        return stop_price_base

    async def _calculate_max_and_min_buy_order_amount_by_symbol(
        self,
        opened_stop_limit_sell_orders: list[Bit2MeOrderDto],
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        *,
        client: AsyncClient,
    ) -> dict[str, tuple[float, float]]:
        sell_order_symbols = set([sell_order.symbol for sell_order in opened_stop_limit_sell_orders])
        opened_buy_orders = await self._bit2me_remote_service.get_pending_buy_orders(client=client)
        # XXX: Discard all buy orders that have higher price than the current corresponding symbol one
        opened_buy_orders = [
            order
            for order in opened_buy_orders
            if order.effective_price < current_tickers_by_symbol[order.symbol].close
        ]
        opened_buy_orders_by_symbol = pydash.group_by(opened_buy_orders, lambda order: order.symbol)
        max_and_min_buy_order_amount_by_symbol = {}
        for sell_order_symbol in sell_order_symbols:
            if sell_order_symbol in opened_buy_orders_by_symbol and opened_buy_orders_by_symbol[sell_order_symbol]:
                max_buy_order = pydash.max_by(
                    opened_buy_orders_by_symbol[sell_order_symbol], lambda order: order.effective_price
                )
                min_buy_order = pydash.min_by(
                    opened_buy_orders_by_symbol[sell_order_symbol], lambda order: order.effective_price
                )
                max_and_min_buy_order_amount_by_symbol[sell_order_symbol] = (
                    max_buy_order.effective_price,
                    min_buy_order.effective_price,
                )
            else:
                max_and_min_buy_order_amount_by_symbol[sell_order_symbol] = (math.inf, math.inf)

        return max_and_min_buy_order_amount_by_symbol
