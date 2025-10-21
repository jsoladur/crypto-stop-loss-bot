from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_account_info_dto import (
    MEXCAccountBalanceDto,
    MEXCAccountInfoDto,
)
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.object_mothers.mexc_account_balance_dto_object_mother import MEXCAccountBalanceDtoObjectMother


class MEXCAccountInfoDtoObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(cls, *, balances: list[MEXCAccountBalanceDto] | None = None) -> MEXCAccountInfoDto:
        return MEXCAccountInfoDto(
            can_trade=True,
            can_withdraw=True,
            can_deposit=True,
            account_type="SPOT",
            balances=balances
            or [
                MEXCAccountBalanceDtoObjectMother.create(currency=current)
                for current in ["USDT"] + MOCK_CRYPTO_CURRENCIES
            ],
            permissions=["SPOT"],
        )
