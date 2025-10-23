from typing import List  # noqa: UP035

from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from tests.helpers.constants import MOCK_SYMBOLS_USDT


class MEXCTickerPriceAndBookDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def list(
        cls, *, symbols: list[str] | None = None, exclude_symbols: list[str] | None = None
    ) -> List[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]]:  # noqa: UP006
        """
        Create a list of Bit2MeTickersDto objects with random values.
        """
        symbols = symbols or MOCK_SYMBOLS_USDT
        exclude_symbols = exclude_symbols or []
        exclude_symbols = (
            list(exclude_symbols) if isinstance(exclude_symbols, (list, set, tuple, frozenset)) else [exclude_symbols]
        )
        return [cls.create(symbol=symbol) for symbol in symbols if symbol not in exclude_symbols]

    @classmethod
    def create(
        cls, *, symbol: str | None = None, close: float | None = None
    ) -> tuple[MEXCTickerPriceDto, MEXCTickerBookDto]:
        """
        Create a Bit2MeTickersDto object with random values.
        """
        close = close or cls._faker.pyfloat(positive=True)
        symbol = "".join((symbol or cls._faker.random_element(MOCK_SYMBOLS_USDT)).split("/"))
        return (
            MEXCTickerPriceDto(symbol=symbol, price=close),
            MEXCTickerBookDto(
                symbol=symbol,
                bid_price=close,
                ask_price=close + cls._faker.pyfloat(positive=True, min_value=0.01, max_value=0.1),
            ),
        )
