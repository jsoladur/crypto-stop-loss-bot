import logging
from datetime import UTC, datetime
from os import listdir
from unittest.mock import patch

import pytest
from aiogram import Bot
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto, Profile
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.constants import BUY_SELL_SIGNALS_MOCK_FILES_PATH, MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, Bit2MeTradingWalletBalanceDtoObjectMother
from tests.helpers.ohlcv_test_utils import load_ohlcv_result_by_filename

logger = logging.getLogger(__name__)


buy_sell_signals_mock_filenames = [
    filename for filename in listdir(BUY_SELL_SIGNALS_MOCK_FILES_PATH) if filename.endswith(".json")
]


@pytest.mark.parametrize(
    "fetch_ohlcv_return_value_filename,enable_adx_filter",
    [(filename, bool_value) for filename in buy_sell_signals_mock_filenames for bool_value in [True, False]],
)
@pytest.mark.asyncio
async def should_send_via_telegram_notifications_after_detecting_buy_sell_signals(
    faker: Faker,
    fetch_ohlcv_return_value_filename: str,
    enable_adx_filter: bool,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env

    application_container = get_application_container()
    task_manager = application_container.infrastructure_container().tasks_container().task_manager()

    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.BUY_SELL_SIGNALS)

    crypto_currency = await _prepare_httpserver_mock(
        faker, httpserver, bit2me_api_key, bit2me_api_secret, fetch_ohlcv_return_value_filename
    )

    buy_sell_signals_task_service: BuySellSignalsTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.BUY_SELL_SIGNALS
    ]
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )
    # Pause job since won't be paused via start(..), stop(..)
    buy_sell_signals_task_service._job.pause()

    if enable_adx_filter:
        buy_sell_signals_config_item: BuySellSignalsConfigItem = (
            buy_sell_signals_config_service._get_defaults_by_symbol(symbol=crypto_currency)
        )
        buy_sell_signals_config_item.enable_adx_filter = True
        await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

    # Provoke send a notification via Telegram
    push_notification = PushNotification(
        {
            PushNotification.telegram_chat_id: faker.random_number(digits=9, fix_len=True),
            PushNotification.notification_type: PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT,
        }
    )
    await push_notification.save()

    with patch.object(
        BuySellSignalsTaskService, "_notify_fatal_error_via_telegram"
    ) as notify_fatal_error_via_telegram_mock:
        if "buy_signal" in fetch_ohlcv_return_value_filename:
            with patch.object(BuySellSignalsTaskService, "_calculate_buy_signal", return_value=True):
                await _run_task_service(buy_sell_signals_task_service)
        elif "sell_signal" in fetch_ohlcv_return_value_filename:
            with patch.object(BuySellSignalsTaskService, "_calculate_sell_signal", return_value=True):
                await _run_task_service(buy_sell_signals_task_service)
        else:
            await _run_task_service(buy_sell_signals_task_service)

        httpserver.check_assertions()
        notify_fatal_error_via_telegram_mock.assert_not_called()


async def _run_task_service(buy_sell_signals_task_service: BuySellSignalsTaskService) -> None:
    with patch.object(Bot, "send_message"):
        await buy_sell_signals_task_service.run()


async def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
    fetch_ohlcv_return_value_filename: str,
) -> None:
    favourite_crypto_currency = await _prepare_favourite_crypto_currency(faker)

    registration_year = datetime.now(UTC).year - 1
    account_info = Bit2MeAccountInfoDto(
        registrationDate=faker.date_time_between_dates(
            datetime_start=datetime(registration_year, 1, 1),
            datetime_end=datetime(registration_year, 12, 31, 23, 59, 59),
        ),
        profile=Profile(currency_code="EUR"),
    )
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = load_ohlcv_result_by_filename(fetch_ohlcv_return_value_filename)
    symbol = f"{favourite_crypto_currency}/{account_info.profile.currency_code}".upper()
    httpserver.expect(
        Bit2MeAPIRequestMatcher(
            "/bit2me-api/v1/trading/candle",
            method="GET",
            query_string=CustomAPIQueryMatcher(
                {"symbol": symbol, "interval": 60, "limit": 251},
                additional_required_query_params=["startTime", "endTime"],
            ),
        ).set_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(fetch_ohlcv_return_value)
    # Trading Wallet Balances
    httpserver.expect(
        Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/wallet/balance", method="GET").set_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeTradingWalletBalanceDto]](
            [Bit2MeTradingWalletBalanceDtoObjectMother.create(currency=favourite_crypto_currency)]
        ).model_dump(mode="json", by_alias=True)
    )

    # Get account info (registration date)
    httpserver.expect(
        Bit2MeAPIRequestMatcher("/bit2me-api/v1/account", method="GET").set_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(account_info.model_dump(mode="json", by_alias=True))

    tickers = Bit2MeTickersDtoObjectMother.create(symbol=symbol)
    rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=symbol)
    tickers_list = [tickers] + rest_tickers
    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMatcher("/bit2me-api/v2/trading/tickers", method="GET").set_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeTickersDto]](tickers_list).model_dump(mode="json", by_alias=True))

    return favourite_crypto_currency


async def _prepare_favourite_crypto_currency(faker: Faker) -> str:
    favourite_crypto_currency = faker.random_element(MOCK_CRYPTO_CURRENCIES)
    favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
        get_application_container().infrastructure_container().services_container().favourite_crypto_currency_service()
    )
    await favourite_crypto_currency_service.add(favourite_crypto_currency)
    return favourite_crypto_currency
