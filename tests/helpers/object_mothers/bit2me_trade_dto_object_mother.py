from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto, Bit2MeTradeSide


class Bit2MeTradeDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        side: Bit2MeTradeSide | None = None,
        symbol: str | None = None,
        price: float | int | None = None,
        amount: float | int | None = None,
    ) -> Bit2MeTradeDto:
        """
        Create a Bit2MeTradeDto object with random values.
        """
        return Bit2MeTradeDto(
            id=cls._faker.uuid4(),
            order_id=cls._faker.uuid4(),
            side=side or cls._faker.random_element(["buy", "sell"]),
            symbol=symbol or cls._faker.random_element(["BTC/EUR", "ETH/EUR"]),
            amount=amount or cls._faker.pyfloat(positive=True, min_value=1_000, max_value=10_000),
            price=price if price is not None else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000),
        )
