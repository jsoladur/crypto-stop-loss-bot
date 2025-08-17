from time import time
from typing import List  # noqa: UP035

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from tests.helpers.constants import MOCK_SYMBOLS


class Bit2MeTickersDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def list(
        cls, *, symbols: list[str] | None = None, exclude_symbols: list[str] | None = None
    ) -> List[Bit2MeTickersDto]:  # noqa: UP006
        """
        Create a list of Bit2MeTickersDto objects with random values.
        """
        symbols = symbols or MOCK_SYMBOLS
        exclude_symbols = exclude_symbols or []
        exclude_symbols = (
            list(exclude_symbols) if isinstance(exclude_symbols, (list, set, tuple, frozenset)) else [exclude_symbols]
        )
        return [cls.create(symbol=symbol) for symbol in symbols if symbol not in exclude_symbols]

    @classmethod
    def create(cls, *, symbol: str | None = None, close: float | None = None) -> Bit2MeTickersDto:
        """
        Create a Bit2MeTickersDto object with random values.
        """
        close = close or cls._faker.pyfloat(positive=True)
        return Bit2MeTickersDto(
            timestamp=int(time()),
            symbol=symbol or cls._faker.random_element(MOCK_SYMBOLS),
            close=close,
            ask=close + cls._faker.pyfloat(positive=True, min_value=0.01, max_value=0.1),
            bid=close,
        )
