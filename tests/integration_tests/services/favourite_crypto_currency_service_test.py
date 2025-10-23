import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_add_and_remove_favourite_crypto_currency_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, *_ = integration_test_jobs_disabled_env

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
