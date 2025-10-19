import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.market_config_utils import load_raw_market_config_list

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_set_buy_sell_signals_config_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env

    _prepare_httpserver_mock(httpserver, bit2me_api_key, bit2me_api_secret)

    operating_exchange_service: AbstractOperatingExchangeService = (
        get_application_container().adapters_container().operating_exchange_service()
    )
    favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
        get_application_container().infrastructure_container().services_container().favourite_crypto_currency_service()
    )

    async with await operating_exchange_service.get_client() as client:
        returned_favourite_crypto_currencies = await favourite_crypto_currency_service.find_all()
        assert len(returned_favourite_crypto_currencies) <= 0
        selected_crypto_currency_to_add = faker.random_element(MOCK_CRYPTO_CURRENCIES)
        non_favourite_crypto_currencies = await favourite_crypto_currency_service.get_non_favourite_crypto_currencies(
            client=client
        )
        assert selected_crypto_currency_to_add in non_favourite_crypto_currencies

        await favourite_crypto_currency_service.add(selected_crypto_currency_to_add)
        returned_favourite_crypto_currencies = await favourite_crypto_currency_service.find_all()
        assert len(returned_favourite_crypto_currencies) == 1
        assert selected_crypto_currency_to_add in returned_favourite_crypto_currencies

        non_favourite_crypto_currencies = await favourite_crypto_currency_service.get_non_favourite_crypto_currencies(
            client=client
        )
        assert selected_crypto_currency_to_add not in non_favourite_crypto_currencies

        await favourite_crypto_currency_service.remove(selected_crypto_currency_to_add)
        returned_favourite_crypto_currencies = await favourite_crypto_currency_service.find_all()
        assert len(returned_favourite_crypto_currencies) <= 0
        assert selected_crypto_currency_to_add not in returned_favourite_crypto_currencies

        non_favourite_crypto_currencies = await favourite_crypto_currency_service.get_non_favourite_crypto_currencies(
            client=client
        )
        assert selected_crypto_currency_to_add in non_favourite_crypto_currencies

        httpserver.check_assertions()


def _prepare_httpserver_mock(httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str) -> list[str]:
    raw_market_config_list = load_raw_market_config_list()
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/market-config", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(raw_market_config_list)
