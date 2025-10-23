from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_account_info_dto import MEXCAccountBalanceDto
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES


class MEXCAccountBalanceDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        *,
        currency: str | None = None,
        balance: float | int | None = None,
        blocked_balance: float | int | None = None,
    ) -> MEXCAccountBalanceDto:
        return MEXCAccountBalanceDto(
            id=cls._faker.uuid4(),
            asset=currency or cls._faker.random_element(MOCK_CRYPTO_CURRENCIES),
            free=balance or cls._faker.pyfloat(positive=True, min_value=100, max_value=1_000, right_digits=2),
            locked=blocked_balance or cls._faker.pyfloat(positive=True, min_value=100, max_value=1_000, right_digits=2),
        )
