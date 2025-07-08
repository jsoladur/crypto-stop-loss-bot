from datetime import UTC, datetime

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.auto_entry_trader_event_handler_service import (
    AutoEntryTraderEventHandlerService,
)
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except


@pytest.mark.asyncio
async def should_create_market_buy_order_and_limit_sell_when_market_buy_1h_signal_is_triggered(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.AUTO_ENTRY_TRADER)
    _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    # Provoke send a notification via Telegram
    telegram_chat_id = faker.random_number(digits=9, fix_len=True)
    for push_notification_type in PushNotificationTypeEnum:
        push_notification = PushNotification(
            {
                PushNotification.telegram_chat_id: telegram_chat_id,
                PushNotification.notification_type: push_notification_type,
            }
        )
        await push_notification.save()

    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
    crypto_currency, *_ = symbol.split("/")
    # Persist 100% FIAT asssigned to the symbol
    auto_buy_trader_config_service = AutoBuyTraderConfigService()
    await auto_buy_trader_config_service.save_or_update(
        AutoBuyTraderConfigItem(symbol=crypto_currency, fiat_wallet_percent_assigned=100)
    )
    # Trigger the event
    auto_entry_trader_event_handler_service = AutoEntryTraderEventHandlerService()
    closing_price = faker.pyfloat(min_value=2_000, max_value=2_200)
    market_signal_item = MarketSignalItem(
        timestamp=datetime.now(UTC),
        symbol=symbol,
        timeframe="1h",
        signal_type="buy",
        rsi_state="neutral",
        atr=faker.pyfloat(min_value=100.0, max_value=200.0),
        closing_price=closing_price,
        ema_long_price=closing_price * 0.9,
    )
    await auto_entry_trader_event_handler_service.on_buy_market_signal(market_signal_item)

    httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
    bit2me_error_status_code: int | None = None,
) -> None:
    pass
