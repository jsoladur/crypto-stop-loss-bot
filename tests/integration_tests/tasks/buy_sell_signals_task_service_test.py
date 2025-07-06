import json
from datetime import UTC, datetime
from os import listdir, path
from typing import Any
from unittest.mock import patch

import ccxt.async_support as ccxt
import pytest
from aiogram import Bot
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto, Profile
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother

BUY_SELL_SIGNALS_MOCK_FILES_PATH = path.realpath(
    path.join(path.dirname(path.abspath(__file__)), "..", "..", "helpers", "resources", "buy_sell_signals_mock_files")
)


@pytest.mark.parametrize(
    "fetch_ohlcv_return_value_filename",
    [filename for filename in listdir(BUY_SELL_SIGNALS_MOCK_FILES_PATH) if filename.endswith(".json")],
)
@pytest.mark.asyncio
async def should_send_via_telegram_notifications_after_detecting_buy_sell_signals(
    faker: Faker, fetch_ohlcv_return_value_filename: str, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.BUY_SELL_SIGNALS)

    task_manager = get_task_manager_instance()
    buy_sell_signals_task_service: BuySellSignalsTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.BUY_SELL_SIGNALS
    ]
    # Pause job since won't be paused via start(..), stop(..)
    buy_sell_signals_task_service._job.pause()

    # Provoke send a notification via Telegram
    push_notification = PushNotification(
        {
            PushNotification.telegram_chat_id: faker.random_number(digits=9, fix_len=True),
            PushNotification.notification_type: PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT,
        }
    )
    await push_notification.save()
    with open(path.join(BUY_SELL_SIGNALS_MOCK_FILES_PATH, fetch_ohlcv_return_value_filename)) as fd:
        fetch_ohlcv_return_value = json.loads(fd.read())

        if "buy_signal" in fetch_ohlcv_return_value_filename:
            with patch.object(BuySellSignalsTaskService, "_calculate_buy_signal", return_value=True):
                await _run_task_service(buy_sell_signals_task_service, fetch_ohlcv_return_value)
        elif "sell_signal" in fetch_ohlcv_return_value_filename:
            with patch.object(BuySellSignalsTaskService, "_calculate_sell_signal", return_value=True):
                await _run_task_service(buy_sell_signals_task_service, fetch_ohlcv_return_value)
        else:
            await _run_task_service(buy_sell_signals_task_service, fetch_ohlcv_return_value)

    httpserver.check_assertions()


async def _run_task_service(
    buy_sell_signals_task_service: BuySellSignalsTaskService, fetch_ohlcv_return_value: dict[str, Any]
) -> None:
    with patch.object(ccxt.binance, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
        with patch.object(Bot, "send_message"):
            await buy_sell_signals_task_service.run()


def _prepare_httpserver_mock(faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str) -> None:
    registration_year = datetime.now(UTC).year - 1
    # Mock call /v1/currency-favorites/favorites
    favourite_crypto_currency = faker.random_element(["BTC", "ETH", "SOL"])
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
