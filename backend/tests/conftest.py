from collections.abc import Generator
from os import environ
from uuid import uuid4

import pytest
from pytest_httpserver import HTTPServer
from faker import Faker


@pytest.fixture(scope="session")
def faker() -> Faker:
    return Faker()


@pytest.fixture(scope="session")
def httpserver_test_env() -> Generator[tuple[HTTPServer, str], None, None]:
    with HTTPServer(threaded=True) as httpserver:
        environ["BIT2ME_API_BASE_URL"] = httpserver.url_for(suffix="/")[:-1]
        bit2me_api_key = environ["BIT2ME_API_KEY"] = str(uuid4())
        bit2me_api_secret = environ["BIT2ME_API_SECRET"] = str(uuid4())

        yield (httpserver, bit2me_api_key, bit2me_api_secret)


@pytest.fixture
def integration_test_env(
    httpserver_test_env: tuple[HTTPServer, str],
) -> Generator[tuple[HTTPServer, str], None, None]:
    httpserver, bit2me_api_key, bit2me_api_secret, *_ = httpserver_test_env
    yield (httpserver, bit2me_api_key, bit2me_api_secret)
    # Cleanup
    httpserver.clear()
