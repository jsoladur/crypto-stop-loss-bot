from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
    Bit2MeOrderSide,
    Bit2MeOrderType,
    Bit2MeOrderStatus,
)
from faker import Faker


class Bit2MeOrderDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        side: Bit2MeOrderSide | None = None,
        symbol: str | None = None,
        order_type: Bit2MeOrderType | None = None,
        status: Bit2MeOrderStatus | None = None,
        price: float | int | None = None,
    ) -> Bit2MeOrderDto:
        """
        Create a Bit2MeOrderDto object with random values.
        """
        order_type = order_type or cls._faker.random_element(
            ["stop-limit", "limit", "market"]
        )
        stop_price = (
            cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000)
            if order_type == "stop-limit"
            else None
        )
        price = (
            price
            if price is not None
            else (
                (stop_price - 1)
                if stop_price
                else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000)
            )
        )
        return Bit2MeOrderDto(
            id=cls._faker.uuid4(),
            side=side or cls._faker.random_element(["buy", "sell"]),
            symbol=symbol or cls._faker.random_element(["BTC/EUR", "ETH/EUR"]),
            order_type=order_type,
            status=status
            or cls._faker.random_element(["open", "filled", "cancelled", "inactive"]),
            order_amount=cls._faker.pyfloat(
                positive=True, min_value=1_000, max_value=10_000
            ),
            stop_price=stop_price,
            price=price,
        )
