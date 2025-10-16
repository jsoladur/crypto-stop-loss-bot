import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.commons.constants import DEFAULT_TRAILING_STOP_LOSS_PERCENT
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_set_stop_loss_percent_service_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env

    stop_loss_percent_service = StopLossPercentService(
        favourite_crypto_currency_service=FavouriteCryptoCurrencyService(bit2me_remote_service=Bit2MeRemoteService()),
        global_flag_service=GlobalFlagService(),
    )
    favourite_crypto_currencies = await _prepare_favourite_crypto_currencies(faker)
    stop_loss_percent_item_list = await stop_loss_percent_service.find_all()
    assert len(stop_loss_percent_item_list) == len(favourite_crypto_currencies)

    crypto_currency = faker.random_element(favourite_crypto_currencies)

    returned_stop_loss_percent_item = await stop_loss_percent_service.find_symbol(crypto_currency)
    assert returned_stop_loss_percent_item is not None
    assert returned_stop_loss_percent_item.symbol == crypto_currency
    assert returned_stop_loss_percent_item.value == DEFAULT_TRAILING_STOP_LOSS_PERCENT

    expected_stop_loss_percent_item = StopLossPercentItem(
        symbol=crypto_currency, value=faker.pyfloat(min_value=1, max_value=5)
    )
    await stop_loss_percent_service.save_or_update(expected_stop_loss_percent_item)
    stop_loss_percent_item_list = await stop_loss_percent_service.find_all()
    assert len(stop_loss_percent_item_list) == len(favourite_crypto_currencies)

    returned_stop_loss_percent_item = await stop_loss_percent_service.find_symbol(crypto_currency)
    assert returned_stop_loss_percent_item is not None
    assert returned_stop_loss_percent_item.symbol == crypto_currency
    assert returned_stop_loss_percent_item.value == expected_stop_loss_percent_item.value


async def _prepare_favourite_crypto_currencies(faker: Faker) -> list[str]:
    favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
        get_application_container().infrastructure_container().services_container().favourite_crypto_currency_service()
    )
    favourite_crypto_currencies = set(faker.random_choices(MOCK_CRYPTO_CURRENCIES, length=3))
    for crypto_currency in favourite_crypto_currencies:
        await favourite_crypto_currency_service.add(crypto_currency)
    return favourite_crypto_currencies
