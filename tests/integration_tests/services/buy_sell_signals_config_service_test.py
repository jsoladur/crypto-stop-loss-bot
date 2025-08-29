import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_set_buy_sell_signals_config_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env

    configuration_properties = get_configuration_properties()

    buy_sell_signals_config_service = BuySellSignalsConfigService(bit2me_remote_service=Bit2MeRemoteService())
    favourite_crypto_currencies = _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    buy_sell_signals_config_list = await buy_sell_signals_config_service.find_all()
    assert len(buy_sell_signals_config_list) == len(favourite_crypto_currencies)

    crypto_currency = faker.random_element(favourite_crypto_currencies)

    returned_buy_sell_signals_config_item = await buy_sell_signals_config_service.find_by_symbol(crypto_currency)
    assert returned_buy_sell_signals_config_item is not None
    assert returned_buy_sell_signals_config_item.symbol == crypto_currency
    assert (
        returned_buy_sell_signals_config_item.ema_short_value
        == configuration_properties.buy_sell_signals_ema_short_value
    )
    assert (
        returned_buy_sell_signals_config_item.ema_mid_value == configuration_properties.buy_sell_signals_ema_mid_value
    )
    assert (
        returned_buy_sell_signals_config_item.ema_long_value == configuration_properties.buy_sell_signals_ema_long_value
    )
    assert (
        returned_buy_sell_signals_config_item.stop_loss_atr_multiplier
        == configuration_properties.suggested_stop_loss_atr_multiplier
    )
    assert (
        returned_buy_sell_signals_config_item.take_profit_atr_multiplier
        == configuration_properties.suggested_take_profit_atr_multiplier
    )
    assert returned_buy_sell_signals_config_item.enable_adx_filter is True
    assert (
        returned_buy_sell_signals_config_item.adx_threshold == configuration_properties.buy_sell_signals_adx_threshold
    )
    assert returned_buy_sell_signals_config_item.enable_buy_volume_filter is True
    assert (
        returned_buy_sell_signals_config_item.min_volume_threshold
        == configuration_properties.buy_sell_signals_min_volume_threshold
    )
    assert returned_buy_sell_signals_config_item.enable_sell_volume_filter is False
    assert (
        returned_buy_sell_signals_config_item.max_volume_threshold
        == configuration_properties.buy_sell_signals_max_volume_threshold
    )
    assert returned_buy_sell_signals_config_item.enable_exit_on_sell_signal is True
    assert returned_buy_sell_signals_config_item.enable_exit_on_take_profit is False

    expected_buy_sell_signals_config_item = BuySellSignalsConfigItem(
        symbol=crypto_currency,
        ema_short_value=faker.pyint(min_value=5, max_value=9),
        ema_mid_value=faker.pyint(min_value=18, max_value=30),
        ema_long_value=faker.pyint(min_value=200, max_value=250),
        stop_loss_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
        take_profit_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
        enable_adx_filter=faker.pybool(truth_probability=99),
        adx_threshold=faker.random_element([15, 20, 25]),
        enable_buy_volume_filter=faker.pybool(truth_probability=1),
        enable_sell_volume_filter=faker.pybool(truth_probability=99),
        min_volume_threshold=faker.pyfloat(min_value=0.25, max_value=0.75),
        max_volume_threshold=faker.pyfloat(min_value=2.5, max_value=5.0),
        enable_exit_on_sell_signal=faker.pybool(truth_probability=1),
        enable_exit_on_take_profit=faker.pybool(truth_probability=99),
    )
    await buy_sell_signals_config_service.save_or_update(expected_buy_sell_signals_config_item)
    buy_sell_signals_config_list = await buy_sell_signals_config_service.find_all()
    assert len(buy_sell_signals_config_list) == len(favourite_crypto_currencies)

    returned_buy_sell_signals_config_item = await buy_sell_signals_config_service.find_by_symbol(crypto_currency)
    assert returned_buy_sell_signals_config_item is not None
    assert returned_buy_sell_signals_config_item.symbol == crypto_currency
    assert (
        returned_buy_sell_signals_config_item.ema_short_value == expected_buy_sell_signals_config_item.ema_short_value
    )
    assert returned_buy_sell_signals_config_item.ema_mid_value == expected_buy_sell_signals_config_item.ema_mid_value
    assert returned_buy_sell_signals_config_item.ema_long_value == expected_buy_sell_signals_config_item.ema_long_value
    assert (
        returned_buy_sell_signals_config_item.stop_loss_atr_multiplier
        == expected_buy_sell_signals_config_item.stop_loss_atr_multiplier
    )
    assert (
        returned_buy_sell_signals_config_item.take_profit_atr_multiplier
        == expected_buy_sell_signals_config_item.take_profit_atr_multiplier
    )
    assert (
        returned_buy_sell_signals_config_item.enable_adx_filter
        == expected_buy_sell_signals_config_item.enable_adx_filter
    )
    assert returned_buy_sell_signals_config_item.adx_threshold == expected_buy_sell_signals_config_item.adx_threshold
    assert (
        returned_buy_sell_signals_config_item.enable_buy_volume_filter
        == expected_buy_sell_signals_config_item.enable_buy_volume_filter
    )
    assert (
        returned_buy_sell_signals_config_item.enable_sell_volume_filter
        == expected_buy_sell_signals_config_item.enable_sell_volume_filter
    )
    assert (
        returned_buy_sell_signals_config_item.min_volume_threshold
        == expected_buy_sell_signals_config_item.min_volume_threshold
    )
    assert (
        returned_buy_sell_signals_config_item.max_volume_threshold
        == expected_buy_sell_signals_config_item.max_volume_threshold
    )
    assert (
        returned_buy_sell_signals_config_item.enable_exit_on_sell_signal
        is expected_buy_sell_signals_config_item.enable_exit_on_sell_signal
    )
    assert (
        returned_buy_sell_signals_config_item.enable_exit_on_take_profit
        == expected_buy_sell_signals_config_item.enable_exit_on_take_profit
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
