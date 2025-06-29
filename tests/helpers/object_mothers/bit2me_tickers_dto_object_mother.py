from time import time

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto


class Bit2MeTickersDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(cls, *, symbol: str | None = None, close: float | None = None) -> Bit2MeTickersDto:
        """
        Create a Bit2MeTickersDto object with random values.
        """
        return Bit2MeTickersDto(
            timestamp=int(time()),
            symbol=symbol or cls._faker.random_element(["BTC-EUR", "ETH-EUR"]),
            close=close or cls._faker.pyfloat(positive=True),
        )
