import pytest
from faker import Faker
from pytest_httpserver import HTTPServer


@pytest.mark.skip(reason="To be implemented!")
@pytest.mark.asyncio
async def should_create_market_sell_order_when_price_goes_down_applying_guard(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    # TODO: To be implemented
    raise NotImplementedError("To be implemented!")
