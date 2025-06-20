from collections.abc import Generator
from os import environ
from uuid import uuid4
from types import ModuleType
from importlib import import_module, reload
import pytest
from pytest_httpserver import HTTPServer
from faker import Faker
from crypto_trailing_stop import config

main_module: ModuleType | None = None


@pytest.fixture(scope="session")
def faker() -> Faker:
    return Faker()


@pytest.fixture(scope="session")
def httpserver_test_env(faker: Faker) -> Generator[tuple[HTTPServer, str], None, None]:
    with HTTPServer(threaded=True) as httpserver:
        # App configuration env variables
        environ["BACKGROUND_TASKS_ENABLED"] = "true"
        # Set up the HTTP server for testing
        environ["BIT2ME_API_BASE_URL"] = httpserver.url_for(suffix="/bit2me-api")
        bit2me_api_key = environ["BIT2ME_API_KEY"] = str(uuid4())
        bit2me_api_secret = environ["BIT2ME_API_SECRET"] = str(uuid4())
        # Telegram bot token is not used in the tests, but it is required for the application to run
        environ["TELEGRAM_BOT_ENABLED"] = "false"
        environ["TELEGRAM_BOT_TOKEN"] = (
            f"{faker.pyint()}:{str(uuid4()).replace('-', '_')}"
        )
        # Google OAuth credentials are not used in the tests, but they are required for the application to run
        environ["GOOGLE_OAUTH_CLIENT_ID"] = str(uuid4())
        environ["GOOGLE_OAUTH_CLIENT_SECRET"] = str(uuid4())

        yield (httpserver, bit2me_api_key, bit2me_api_secret)


@pytest.fixture
def integration_test_env(
    httpserver_test_env: tuple[HTTPServer, str],
) -> Generator[tuple[HTTPServer, str], None, None]:
    global main_module
    httpserver, bit2me_api_key, bit2me_api_secret, *_ = httpserver_test_env

    if main_module:
        main_module = reload(main_module)
    else:
        main_module = import_module("crypto_trailing_stop.main")

    yield (main_module.app, httpserver, bit2me_api_key, bit2me_api_secret)

    # Cleanup
    httpserver.clear()
    reload(config)
