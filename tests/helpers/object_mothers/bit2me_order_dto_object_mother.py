from datetime import UTC, datetime

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
    Bit2MeOrderSide,
    Bit2MeOrderStatus,
    Bit2MeOrderType,
)


class Bit2MeOrderDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        created_at: datetime | None = None,
        side: Bit2MeOrderSide | None = None,
        symbol: str | None = None,
        order_type: Bit2MeOrderType | None = None,
        status: Bit2MeOrderStatus | None = None,
        order_amount: float | int | None = None,
        stop_price: float | int | None = None,
        price: float | int | None = None,
    ) -> Bit2MeOrderDto:
        """
        Create a Bit2MeOrderDto object with random values.
        """
        order_type = order_type or cls._faker.random_element(["stop-limit", "limit", "market"])
        stop_price = (
            stop_price
            or ((price - 1) if price is not None else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000))
            if order_type == "stop-limit"
            else None
        )
        price = (
            price
            if price is not None
            else ((stop_price + 1) if stop_price else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000))
        )
        return Bit2MeOrderDto(
            id=cls._faker.uuid4(),
            created_at=created_at or cls._faker.past_datetime(tzinfo=UTC),
            side=side or cls._faker.random_element(["buy", "sell"]),
            symbol=symbol or cls._faker.random_element(["ETH/EUR", "SOL/EUR"]),
            order_type=order_type,
            status=status or cls._faker.random_element(["open", "filled", "cancelled", "inactive"]),
            order_amount=order_amount or cls._faker.pyfloat(positive=True, min_value=1_000, max_value=10_000),
            stop_price=stop_price,
            price=price,
        )
