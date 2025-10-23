from datetime import UTC, datetime
from typing import get_args

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import (
    MEXCOrderDto,
    MEXCOrderSide,
    MEXCOrderStatus,
    MEXCOrderType,
)
from tests.helpers.constants import MOCK_SYMBOLS_USDT


class MEXCOrderDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        created_at: datetime | None = None,
        side: MEXCOrderSide | None = None,
        symbol: str | None = None,
        order_type: MEXCOrderType | None = None,
        status: MEXCOrderStatus | None = None,
        order_amount: float | int | None = None,
        stop_price: float | int | None = None,
        price: float | int | None = None,
    ) -> MEXCOrderDto:
        """
        Create a Bit2MeOrderDto object with random values.
        """
        symbol = "".join((symbol or cls._faker.random_element(MOCK_SYMBOLS_USDT)).split("/"))
        order_type = order_type or cls._faker.random_element(list(get_args(MEXCOrderType)))
        stop_price = (
            stop_price
            or ((price - 1) if price is not None else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000))
            if order_type == "STOP_LIMIT"
            else None
        )
        price = (
            price
            if price is not None
            else ((stop_price + 1) if stop_price else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000))
        )
        order_amount = order_amount or cls._faker.pyfloat(positive=True, min_value=1_000, max_value=10_000)
        qty = str(order_amount) if order_amount else None
        ret = MEXCOrderDto(
            order_id=cls._faker.pyint(min_value=1_000_000, max_value=9_999_999)
            if cls._faker.pybool()
            else cls._faker.uuid4(),
            side=side or cls._faker.random_element(["buy", "sell"]),
            symbol=symbol,
            type=order_type,
            time=int((created_at or cls._faker.past_datetime(tzinfo=UTC)).timestamp() * 1000),
            status=status or cls._faker.random_element(list(get_args(MEXCOrderStatus))),
            price=str(price) if price else None,
            qty=qty,
            executed_qty=qty,
            stop_price=str(stop_price) if stop_price else None,
        )
        return ret
