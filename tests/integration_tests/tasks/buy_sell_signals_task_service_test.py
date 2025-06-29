import pytest
from faker import Faker
from pytest_httpserver import HTTPServer


@pytest.mark.skip(reason="To be implemented!")
@pytest.mark.asyncio
async def should_send_via_telegram_notifications_after_detecting_buy_sell_signals(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    # TODO: To be implemented
    raise NotImplementedError("To be implemented!")
