import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_set_auto_buy_trader_config_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env

    auto_buy_trader_config_service = AutoBuyTraderConfigService(bit2me_remote_service=Bit2MeRemoteService())
    favourite_crypto_currencies = _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
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

    httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> list[str]:
    # Mock call /v1/currency-favorites/favorites
    favourite_crypto_currencies = set(faker.random_choices(MOCK_CRYPTO_CURRENCIES, length=3))
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/currency-favorites/favorites", method="GET"
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(
        [{"currency": favourite_crypto_currency} for favourite_crypto_currency in favourite_crypto_currencies]
    )

    return favourite_crypto_currencies
