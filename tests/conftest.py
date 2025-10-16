from collections.abc import AsyncGenerator, Generator
from importlib import import_module, reload
from os import environ
from tempfile import NamedTemporaryFile
from types import ModuleType
from unittest.mock import patch
from uuid import uuid4

import ccxt.async_support as ccxt
import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop import config
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.market_config_utils import load_raw_market_config_list

main_module: ModuleType | None = None


@pytest.fixture(scope="session")
def faker() -> Faker:
    return Faker()


@pytest.fixture(scope="session", autouse=True)
def defaults_env(faker: Faker) -> Generator[None]:
    # App configuration
    environ["LOGIN_ENABLED"] = "true"
    # Background jobs configuration
    environ["BUY_SELL_SIGNALS_RUN_VIA_CRON_PATTERN"] = "false"
    # Database configuration
    environ["DATABASE_IN_MEMORY"] = "false"
    # Telegram bot token is not used in the tests, but it is required for the application to run
    environ["TELEGRAM_BOT_ENABLED"] = "false"
    environ["TELEGRAM_BOT_TOKEN"] = f"{faker.pyint()}:{str(uuid4()).replace('-', '_')}"
    # Google OAuth credentials are not used in the tests, but they are required for the application to run
    environ["AUTHORIZED_GOOGLE_USER_EMAILS_COMMA_SEPARATED"] = ",".join(
        [faker.email(domain="gmail.com") for _ in range(faker.pyint(min_value=1, max_value=3))]
    )
    environ["GOOGLE_OAUTH_CLIENT_ID"] = str(uuid4())
    environ["GOOGLE_OAUTH_CLIENT_SECRET"] = str(uuid4())


@pytest.fixture(scope="session")
def httpserver_test_env() -> Generator[tuple[HTTPServer, ...]]:
    with HTTPServer() as httpserver:
        # Set up the HTTP server for testing
        environ["BIT2ME_API_BASE_URL"] = httpserver.url_for(suffix="/bit2me-api")
        bit2me_api_key = environ["BIT2ME_API_KEY"] = str(uuid4())
        bit2me_api_secret = environ["BIT2ME_API_SECRET"] = str(uuid4())

        yield (httpserver, bit2me_api_key, bit2me_api_secret)


@pytest.fixture(autouse=True)
def database_path_env() -> Generator[None]:
    with NamedTemporaryFile(suffix=".sqlite") as temp_db:
        environ["DATABASE_PATH"] = temp_db.name
        yield


@pytest.fixture
async def integration_test_jobs_disabled_env(
    httpserver_test_env: tuple[HTTPServer, str],
) -> AsyncGenerator[tuple[FastAPI, ...]]:
    global main_module
    httpserver, bit2me_api_key, bit2me_api_secret, *_ = httpserver_test_env
    # XXX: Disable background tasks
    environ["BACKGROUND_TASKS_ENABLED"] = "false"
    if main_module:
        main_module = reload(main_module)
    else:
        main_module = import_module("crypto_trailing_stop.main")
    async with LifespanManager(main_module.app) as manager:
        with patch.object(ccxt.binance, "load_markets", return_value={}):
            _prepare_global_httpserver_mock_requests(faker, httpserver, bit2me_api_key, bit2me_api_secret)
            yield (manager.app, httpserver, bit2me_api_key, bit2me_api_secret)
    # Cleanup
    _cleanup(httpserver)


@pytest.fixture
async def integration_test_env(
    faker: Faker, httpserver_test_env: tuple[HTTPServer, str]
) -> AsyncGenerator[tuple[FastAPI, ...]]:
    global main_module
    httpserver, bit2me_api_key, bit2me_api_secret, *_ = httpserver_test_env
    # XXX: Enable background tasks
    environ["BACKGROUND_TASKS_ENABLED"] = "true"
    if main_module:
        main_module = reload(main_module)
    else:
        main_module = import_module("crypto_trailing_stop.main")
    async with LifespanManager(main_module.app) as manager:
        with patch.object(ccxt.binance, "load_markets", return_value={}):
            _prepare_global_httpserver_mock_requests(faker, httpserver, bit2me_api_key, bit2me_api_secret)
            yield (manager.app, httpserver, bit2me_api_key, bit2me_api_secret)
    # Cleanup
    _cleanup(httpserver)


def _prepare_global_httpserver_mock_requests(
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> None:
    raw_market_config_list = load_raw_market_config_list()
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/market-config", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(raw_market_config_list)


def _cleanup(httpserver: HTTPServer) -> None:
    from crypto_trailing_stop.config.dependencies import get_application_container

    application_container = get_application_container()
    application_container.reset_singletons()
    httpserver.clear()
    reload(config)
