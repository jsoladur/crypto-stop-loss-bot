import logging
from os import listdir
from unittest.mock import patch

import ccxt.async_support as ccxt
import pytest
from aiogram import Bot
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.constants import BUY_SELL_SIGNALS_MOCK_FILES_PATH
from tests.helpers.favourite_crypto_currencies_test_utils import prepare_favourite_crypto_currencies
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_account_info_mock,
    prepare_httpserver_fetch_ohlcv_mock,
    prepare_httpserver_tickers_list_mock,
    prepare_httpserver_trading_wallet_balances_mock,
)
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, MEXCTickerPriceAndBookDtoObjectMother
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
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env

    application_container = get_application_container()
    task_manager = application_container.infrastructure_container().tasks_container().task_manager()

    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.BUY_SELL_SIGNALS)

    crypto_currency, fetch_ohlcv_return_value, *_ = await _prepare_httpserver_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, fetch_ohlcv_return_value_filename
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

    if operating_exchange == OperatingExchangeEnum.MEXC:
        with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
            await _exec_test(httpserver, buy_sell_signals_task_service, fetch_ohlcv_return_value_filename)
    else:
        await _exec_test(httpserver, buy_sell_signals_task_service, fetch_ohlcv_return_value_filename)


async def _exec_test(
    httpserver: HTTPServer,
    buy_sell_signals_task_service: BuySellSignalsTaskService,
    fetch_ohlcv_return_value_filename: str,
) -> None:
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
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    fetch_ohlcv_return_value_filename: str,
) -> None:
    favourite_crypto_currency, *_ = await prepare_favourite_crypto_currencies(faker, length=1)

    account_info = prepare_httpserver_account_info_mock(faker, httpserver, operating_exchange, api_key, api_secret)
    symbol = f"{favourite_crypto_currency}/{account_info.currency_code}".upper()
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = load_ohlcv_result_by_filename(fetch_ohlcv_return_value_filename)
    prepare_httpserver_fetch_ohlcv_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        symbol,
        fetch_ohlcv_return_value=fetch_ohlcv_return_value,
        intervals=[60, 240],
    )
    # Trading Wallet Balances
    prepare_httpserver_trading_wallet_balances_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        wallet_balances_crypto_currencies=[favourite_crypto_currency],
    )

    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        tickers = Bit2MeTickersDtoObjectMother.create(symbol=symbol)
        rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        tickers = MEXCTickerPriceAndBookDtoObjectMother.create(symbol=symbol)
        rest_tickers = MEXCTickerPriceAndBookDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
    prepare_httpserver_tickers_list_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        tickers_list=tickers_list,
        handler_type=HandlerType.ONESHOT,
    )
    return favourite_crypto_currency, fetch_ohlcv_return_value
