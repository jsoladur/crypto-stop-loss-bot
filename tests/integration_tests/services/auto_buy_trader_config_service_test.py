import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_set_auto_buy_trader_config_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env

    auto_buy_trader_config_service: AutoBuyTraderConfigService = (
        get_application_container().infrastructure_container().services_container().auto_buy_trader_config_service()
    )
    favourite_crypto_currencies = await _prepare_favourite_crypto_currencies(faker)
    auto_buy_trader_config_list = await auto_buy_trader_config_service.find_all()
    assert len(auto_buy_trader_config_list) == len(favourite_crypto_currencies)

    crypto_currency = faker.random_element(favourite_crypto_currencies)

    returned_auto_buy_trader_config_item = await auto_buy_trader_config_service.find_by_symbol(crypto_currency)
    assert returned_auto_buy_trader_config_item is not None
    assert returned_auto_buy_trader_config_item.symbol == crypto_currency
    assert returned_auto_buy_trader_config_item.fiat_wallet_percent_assigned == 0

    expected_auto_buy_trader_config_item = AutoBuyTraderConfigItem(
        symbol=crypto_currency, fiat_wallet_percent_assigned=faker.pyint(min_value=25, max_value=100)
    )
    await auto_buy_trader_config_service.save_or_update(expected_auto_buy_trader_config_item)
    auto_buy_trader_config_list = await auto_buy_trader_config_service.find_all()
    assert len(auto_buy_trader_config_list) == len(favourite_crypto_currencies)

    returned_auto_buy_trader_config_item = await auto_buy_trader_config_service.find_by_symbol(crypto_currency)
    assert returned_auto_buy_trader_config_item is not None
    assert returned_auto_buy_trader_config_item.symbol == crypto_currency
    assert (
        returned_auto_buy_trader_config_item.fiat_wallet_percent_assigned
        == expected_auto_buy_trader_config_item.fiat_wallet_percent_assigned
    )


async def _prepare_favourite_crypto_currencies(faker: Faker) -> list[str]:
    favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
        get_application_container().infrastructure_container().services_container().favourite_crypto_currency_service()
    )
    favourite_crypto_currencies = set(faker.random_choices(MOCK_CRYPTO_CURRENCIES, length=3))
    for crypto_currency in favourite_crypto_currencies:
        await favourite_crypto_currency_service.add(crypto_currency)
    return favourite_crypto_currencies
