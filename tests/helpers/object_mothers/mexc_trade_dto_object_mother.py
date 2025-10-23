from datetime import UTC, datetime

from faker import Faker

from crypto_trailing_stop.commons.constants import MEXC_TAKER_FEES
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_trade_dto import MEXCTradeDto
from tests.helpers.constants import MOCK_SYMBOLS_USDT


class MEXCTradeDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        is_buyer: bool | None = None,
        symbol: str | None = None,
        price: float | int | None = None,
        amount: float | int | None = None,
    ) -> MEXCTradeDto:
        """
        Create a MEXCTradeDto object with random values.
        """
        symbol = "".join((symbol or cls._faker.random_element(MOCK_SYMBOLS_USDT)).split("/"))
        amount = amount or cls._faker.pyfloat(positive=True, min_value=1_000, max_value=10_000)
        fee_amount = (amount * (1 + MEXC_TAKER_FEES)) - amount
        return MEXCTradeDto(
            id=cls._faker.uuid4(),
            time=int(datetime.now(tz=UTC).timestamp() * 1000),
            symbol=symbol,
            order_id=cls._faker.uuid4(),
            price=price if price is not None else cls._faker.pyfloat(positive=True, min_value=500, max_value=1_000),
            qty=amount,
            commission=fee_amount,
            is_buyer=is_buyer if is_buyer is not None else cls._faker.boolean(),
        )
