import logging
from urllib.parse import urlencode

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_porfolio_balance_dto import (
    Bit2MePortfolioBalanceDto,
    ConvertedBalanceDto,
    TotalDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_contract_asset_dto import MEXCContractAssetDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, MEXCContractRequestMatcher
from tests.helpers.httpserver_pytest.utils.trading_wallet_balances_mock import (
    prepare_httpserver_trading_wallet_balances_mock,
)

logger = logging.getLogger(__name__)


def prepare_httpserver_retrieve_portfolio_balance_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    user_currency: str | None = None,
    global_portfolio_balance: float | None = None,
    wallet_balances_crypto_currencies: list[str] | None = None,
) -> None:
    global_portfolio_balance = global_portfolio_balance or faker.pyfloat(min_value=1_000, max_value=3_000)
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            user_currency = user_currency or "EUR"
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    "/bit2me-api/v1/portfolio/balance",
                    query_string=urlencode({"userCurrency": user_currency}, doseq=False),
                    method="GET",
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[Bit2MePortfolioBalanceDto]](
                    [
                        Bit2MePortfolioBalanceDto(
                            serviceName="all",
                            total=TotalDto(
                                converted_balance=ConvertedBalanceDto(currency="EUR", value=global_portfolio_balance)
                            ),
                            wallets=[],
                        )
                    ]
                ).model_dump(mode="json", by_alias=True)
            )
        case OperatingExchangeEnum.MEXC:
            prepare_httpserver_trading_wallet_balances_mock(
                faker,
                httpserver,
                operating_exchange,
                api_key,
                api_secret,
                wallet_balances_crypto_currencies=wallet_balances_crypto_currencies or ["USDT"],
                fixed_balance=global_portfolio_balance,
            )
            # Simulate access to
            httpserver.expect(
                MEXCContractRequestMatcher(
                    "/mexc-contract-api/api/v1/private/account/assets", method="GET"
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[MEXCContractAssetDto]]([MEXCContractAssetDto(asset="USDT")]).model_dump(
                    mode="json", by_alias=True
                )
            )
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
