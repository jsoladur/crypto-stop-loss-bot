import pytest
from pytest_httpserver import HTTPServer
from faker import Faker


@pytest.mark.skip(reason="To be implemented!")
@pytest.mark.asyncio
async def should_make_all_expected_calls_to_bit2me_when_trailing_stop_loss(
    faker: Faker,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    # TODO: To be implemented
    raise NotImplementedError("To be implemented!")
