from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES


class Bit2MeTradingWalletBalanceDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        currency: str | None = None,
        balance: float | int | None = None,
        blocked_balance: float | int | None = None,
    ) -> Bit2MeTradingWalletBalanceDto:
        return Bit2MeTradingWalletBalanceDto(
            id=cls._faker.uuid4(),
            currency=currency or cls._faker.random_element(MOCK_CRYPTO_CURRENCIES),
            balance=balance or cls._faker.pyfloat(positive=True, min_value=100, max_value=1_000, right_digits=2),
            blocked_balance=blocked_balance
            or cls._faker.pyfloat(positive=True, min_value=100, max_value=1_000, right_digits=2),
        )
