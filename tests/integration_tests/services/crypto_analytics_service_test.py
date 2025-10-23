import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from tests.helpers.favourite_crypto_currencies_test_utils import prepare_favourite_crypto_currencies
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_account_info_mock,
    prepare_httpserver_tickers_list_mock,
    prepare_httpserver_trading_wallet_balances_mock,
)
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, MEXCTickerPriceAndBookDtoObjectMother

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_get_favourite_symbols_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_jobs_disabled_env
    _, favourite_crypto_currencies, account_info = await _prepare_httpserver_mock_for_favourite_symbols(
        faker, httpserver, operating_exchange, api_key, api_secret
    )
    crypto_analytics_service: CryptoAnalyticsService = (
        get_application_container().infrastructure_container().services_container().crypto_analytics_service()
    )
    favourite_symbols = await crypto_analytics_service.get_favourite_symbols()
    expected_symbols = [
        f"{crypto_currency}/{account_info.currency_code}" for crypto_currency in favourite_crypto_currencies
    ]
    assert all(favourite_symbol in expected_symbols for favourite_symbol in favourite_symbols)
    httpserver.check_assertions()


@pytest.mark.asyncio
async def should_get_favourite_tickers_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_jobs_disabled_env
    await _prepare_httpserver_mock_for_get_favourite_tickers(faker, httpserver, operating_exchange, api_key, api_secret)
    crypto_analytics_service: CryptoAnalyticsService = (
        get_application_container().infrastructure_container().services_container().crypto_analytics_service()
    )
    tickers_list = await crypto_analytics_service.get_favourite_tickers()
    assert tickers_list is not None and len(tickers_list) > 0
    httpserver.check_assertions()


async def _prepare_httpserver_mock_for_get_favourite_tickers(
    faker: Faker, httpserver: HTTPServer, operating_exchange: OperatingExchangeEnum, api_key: str, api_secret: str
) -> None:
    _, favourite_crypto_currencies, account_info = await _prepare_httpserver_mock_for_favourite_symbols(
        faker, httpserver, operating_exchange, api_key, api_secret
    )
    symbols = symbols = [
        f"{crypto_currency}/{account_info.currency_code}" for crypto_currency in favourite_crypto_currencies
    ]
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        tickers_list = Bit2MeTickersDtoObjectMother.list(symbols=symbols)
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        tickers_list = MEXCTickerPriceAndBookDtoObjectMother.list(symbols=symbols)
    else:
        raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    prepare_httpserver_tickers_list_mock(
        faker, httpserver, operating_exchange, api_key, api_secret=api_secret, tickers_list=tickers_list
    )


async def _prepare_httpserver_mock_for_favourite_symbols(
    faker: Faker, httpserver: HTTPServer, operating_exchange: OperatingExchangeEnum, api_key: str, api_secret: str
) -> tuple[str, list[str]]:
    favourite_crypto_currencies = await prepare_favourite_crypto_currencies(faker)
    favourite_crypto_currency = faker.random_element(favourite_crypto_currencies)
    account_info = prepare_httpserver_account_info_mock(faker, httpserver, operating_exchange, api_key, api_secret)
    wallet_balances_crypto_currencies = [
        current for current in favourite_crypto_currencies if current != favourite_crypto_currency
    ]
    # Trading Wallet Balances
    prepare_httpserver_trading_wallet_balances_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        wallet_balances_crypto_currencies=wallet_balances_crypto_currencies,
    )
    return favourite_crypto_currency, favourite_crypto_currencies, account_info
