from time import time

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES


class Bit2MeTickersDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(cls, *, symbol: str | None = None, close: float | None = None) -> Bit2MeTickersDto:
        """
        Create a Bit2MeTickersDto object with random values.
        """
        close = close or cls._faker.pyfloat(positive=True)
        return Bit2MeTickersDto(
            timestamp=int(time()),
            symbol=symbol
            or cls._faker.random_element([f"{crypto_currency}/EUR" for crypto_currency in MOCK_CRYPTO_CURRENCIES]),
            close=close,
            ask=close + cls._faker.pyfloat(positive=True, min_value=0.01, max_value=0.1),
            bid=close - cls._faker.pyfloat(positive=True, min_value=0.01, max_value=0.1),
        )
