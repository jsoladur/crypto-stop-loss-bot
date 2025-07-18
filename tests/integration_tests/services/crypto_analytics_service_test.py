import logging
from datetime import UTC, datetime

import pytest
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto, Profile
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, Bit2MeTradingWalletBalanceDtoObjectMother

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_get_favourite_symbols_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env
    _, favourite_crypto_currencies, account_info = _prepare_httpserver_mock_for_favourite_symbols(
        faker, httpserver, bit2me_api_key, bit2me_api_secret
    )
    bit2me_remote_service = Bit2MeRemoteService()
    crypto_analytics_service = CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=CcxtRemoteService(),
        buy_sell_signals_config_service=BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service),
    )
    favourite_symbols = await crypto_analytics_service.get_favourite_symbols()
    expected_symbols = [
        f"{crypto_currency}/{account_info.profile.currency_code}" for crypto_currency in favourite_crypto_currencies
    ]
    assert all(favourite_symbol in expected_symbols for favourite_symbol in favourite_symbols)
    httpserver.check_assertions()


@pytest.mark.asyncio
async def should_get_favourite_tickers_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env
    _prepare_httpserver_mock_for_get_favourite_tickers(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    bit2me_remote_service = (Bit2MeRemoteService(),)
    crypto_analytics_service = CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=CcxtRemoteService(),
        buy_sell_signals_config_service=BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service),
    )
    tickers_list = await crypto_analytics_service.get_favourite_tickers()
    assert tickers_list is not None and len(tickers_list) > 0
    httpserver.check_assertions()


def _prepare_httpserver_mock_for_get_favourite_tickers(
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> None:
    _, favourite_crypto_currencies, account_info = _prepare_httpserver_mock_for_favourite_symbols(
        faker, httpserver, bit2me_api_key, bik2me_api_secret
    )
    for favourite_crypto_currency in favourite_crypto_currencies:
        tickers = Bit2MeTickersDtoObjectMother.create(
            symbol=f"{favourite_crypto_currency}/{account_info.profile.currency_code}"
        )
        # Mock call to /v2/trading/tickers
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v2/trading/tickers", method="GET", query_string={"symbol": tickers.symbol}
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(RootModel[list[Bit2MeTickersDto]]([tickers]).model_dump(mode="json", by_alias=True))


def _prepare_httpserver_mock_for_favourite_symbols(
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> tuple[str, list[str, Bit2MeAccountInfoDto]]:
    registration_year = datetime.now(UTC).year - 1
    # Mock call /v1/currency-favorites/favorites

    favourite_crypto_currencies = faker.random_choices(
        MOCK_CRYPTO_CURRENCIES, length=faker.pyint(min_value=2, max_value=len(MOCK_CRYPTO_CURRENCIES) - 1)
    )
    favourite_crypto_currency = faker.random_element(favourite_crypto_currencies)

    account_info = Bit2MeAccountInfoDto(
        registrationDate=faker.date_time_between_dates(
            datetime_start=datetime(registration_year, 1, 1),
            datetime_end=datetime(registration_year, 12, 31, 23, 59, 59),
        ),
        profile=Profile(currency_code="EUR"),
    )
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/currency-favorites/favorites", method="GET"
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json([{"currency": favourite_crypto_currency}])
    # Get account registration date
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v1/account", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(account_info.model_dump(mode="json", by_alias=True))

    # Trading Wallet Balances
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/wallet/balance", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeTradingWalletBalanceDto]](
            [
                Bit2MeTradingWalletBalanceDtoObjectMother.create(currency=current)
                for current in favourite_crypto_currencies
                if current != favourite_crypto_currency
            ]
        ).model_dump(mode="json", by_alias=True)
    )
    return favourite_crypto_currency, favourite_crypto_currencies, account_info
