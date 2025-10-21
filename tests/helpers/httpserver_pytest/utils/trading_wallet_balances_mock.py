import logging

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher
from tests.helpers.object_mothers import Bit2MeTradingWalletBalanceDtoObjectMother

logger = logging.getLogger(__name__)


def prepare_httpserver_trading_wallet_balances_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    wallet_balances_crypto_currencies: list[str] | None = None,
) -> list[str]:
    wallet_balances_crypto_currencies = wallet_balances_crypto_currencies or faker.random_choices(
        MOCK_CRYPTO_CURRENCIES, length=faker.pyint(min_value=2, max_value=len(MOCK_CRYPTO_CURRENCIES) - 1)
    )
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/wallet/balance", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[Bit2MeTradingWalletBalanceDto]](
                    [
                        Bit2MeTradingWalletBalanceDtoObjectMother.create(currency=current)
                        for current in wallet_balances_crypto_currencies
                    ]
                ).model_dump(mode="json", by_alias=True)
            )
        case OperatingExchangeEnum.MEXC:
            raise NotImplementedError("FIXME: To be implemented!")
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    return wallet_balances_crypto_currencies
