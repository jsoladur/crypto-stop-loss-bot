import pytest
from asyncio import sleep
from pytest_httpserver import HTTPServer
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
)
from asgi_lifespan import LifespanManager
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from httpx import AsyncClient, ASGITransport
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response
from pydantic import RootModel
from faker import Faker
from tests.helpers.constants import MAX_SECONDS


@pytest.mark.asyncio
async def should_make_all_expected_calls_to_bit2me_when_trailing_stop_lost(
    faker: Faker,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a trailing stop is lost.
    """
    # Mock the Bit2Me API
    httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env

    _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)

    from crypto_trailing_stop.main import app

    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            for _ in range(MAX_SECONDS):
                # Call the function that triggers the trailing stop lost
                response = await client.get("/health/status")
                response.raise_for_status()
                await sleep(delay=1.0)

    httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> None:
    bit2me_order = Bit2MeOrderDtoObjectMother.create(
        side="sell",
        order_type="stop-limit",
        status=faker.random_element(["open", "inactive"]),
    )
    bit2me_tickers = Bit2MeTickersDtoObjectMother.create(
        symbol=bit2me_order.symbol,
        close=(
            bit2me_order.stop_price + faker.pyfloat(min_value=10.000, max_value=100.000)
        ),
    )

    # Mock call to /v1/trading/order
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string={
                "direction": "desc",
                "status_in": "open,inactive",
                "side": "sell",
                "orderType": "stop-limit",
            },
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]]([bit2me_order]).model_dump(
            mode="json", by_alias=True
        ),
    )

    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v2/trading/tickers",
            method="GET",
            query_string={"symbol": bit2me_order.symbol},
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(
        RootModel[list[Bit2MeTickersDto]]([bit2me_tickers]).model_dump(
            mode="json", by_alias=True
        ),
    )

    # Mock call to DELETE /v1/trading/order/{id}
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            f"/bit2me-api/v1/trading/order/{str(bit2me_order.id)}",
            method="DELETE",
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_response(Response(status=204))

    # Mock call to POST /v1/trading/order
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="POST",
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(
        Bit2MeOrderDtoObjectMother.create(
            side="sell",
            order_type="stop-limit",
            status=faker.random_element(["open", "inactive"]),
        ).model_dump(by_alias=True, mode="json")
    )
