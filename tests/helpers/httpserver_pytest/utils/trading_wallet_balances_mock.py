import logging

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_account_info_dto import MEXCAccountBalanceDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, MEXCAPIRequestMatcher
from tests.helpers.object_mothers import (
    Bit2MeTradingWalletBalanceDtoObjectMother,
    MEXCAccountBalanceDtoObjectMother,
    MEXCAccountInfoDtoObjectMother,
)

logger = logging.getLogger(__name__)


def prepare_httpserver_trading_wallet_balances_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    wallet_balances_objects: list[Bit2MeTradingWalletBalanceDto] | list[MEXCAccountBalanceDto] | None = None,
    wallet_balances_crypto_currencies: list[str] | None = None,
    fixed_balance: float | None = None,
) -> list[str]:
    wallet_balances_crypto_currencies = wallet_balances_crypto_currencies or faker.random_choices(
        MOCK_CRYPTO_CURRENCIES, length=faker.pyint(min_value=2, max_value=len(MOCK_CRYPTO_CURRENCIES) - 1)
    )
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            wallet_balances_objects = wallet_balances_objects or [
                Bit2MeTradingWalletBalanceDtoObjectMother.create(currency=current, balance=fixed_balance)
                for current in wallet_balances_crypto_currencies
            ]
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/wallet/balance", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[Bit2MeTradingWalletBalanceDto]](wallet_balances_objects).model_dump(
                    mode="json", by_alias=True
                )
            )
        case OperatingExchangeEnum.MEXC:
            wallet_balances_objects = wallet_balances_objects or [
                MEXCAccountBalanceDtoObjectMother.create(currency=current, balance=fixed_balance)
                for current in wallet_balances_crypto_currencies
            ]
            mexc_account_info = MEXCAccountInfoDtoObjectMother.create(balances=wallet_balances_objects)
            httpserver.expect(
                MEXCAPIRequestMatcher("/mexc-api/api/v3/account", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(mexc_account_info.model_dump(mode="json", by_alias=True))
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    return wallet_balances_crypto_currencies
