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
        order_type: Bit2MeOrderType | None = None,
        status: Bit2MeOrderStatus | None = None,
    ) -> Bit2MeOrderDto:
        """
        Create a Bit2MeOrderDto object with random values.
        """
        stop_price = cls._faker.pyfloat(positive=True, max_value=1.000)
        return Bit2MeOrderDto(
            id=cls._faker.uuid4(),
            side=side or cls._faker.random_element(["buy", "sell"]),
            symbol=cls._faker.random_element(["BTC-EUR", "ETH-EUR"]),
            order_type=order_type
            or cls._faker.random_element(["stop-limit", "limit", "market"]),
            status=status
            or cls._faker.random_element(["open", "filled", "cancelled", "inactive"]),
            order_amount=cls._faker.pyfloat(positive=True),
            stop_price=stop_price,
            price=(stop_price - 1),
        )
