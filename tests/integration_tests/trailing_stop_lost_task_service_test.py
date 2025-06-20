import pytest
from asyncio import sleep
from pytest_httpserver import HTTPServer
from urllib.parse import urlencode
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


@pytest.mark.parametrize("simulate_pending_buy_orders_to_filled", [True, False])
@pytest.mark.asyncio
async def should_make_all_expected_calls_to_bit2me_when_trailing_stop_loss(
    faker: Faker,
    simulate_pending_buy_orders_to_filled: bool,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a trailing stop is lost.
    """
    # Mock the Bit2Me API
    app, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env

    _prepare_httpserver_mock(
        faker,
        simulate_pending_buy_orders_to_filled,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
    )

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
    faker: Faker,
    simulate_pending_buy_orders_to_filled: bool,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
) -> None:
    opened_sell_bit2me_order = Bit2MeOrderDtoObjectMother.create(
        side="sell",
        order_type="stop-limit",
        status=faker.random_element(["open", "inactive"]),
    )
    # Mock call to /v1/trading/order to get opened buy orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode(
                {
                    "direction": "desc",
                    "status_in": "open,inactive",
                    "side": "buy",
                },
                doseq=False,
            ),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]](
            [
                Bit2MeOrderDtoObjectMother.create(
                    side="buy",
                    symbol=opened_sell_bit2me_order.symbol,
                    order_type="limit",
                    status=faker.random_element(["open", "inactive"]),
                    price=opened_sell_bit2me_order.price
                    * faker.pyfloat(min_value=0.20, max_value=0.40),
                ),
                Bit2MeOrderDtoObjectMother.create(
                    side="buy",
                    symbol=opened_sell_bit2me_order.symbol,
                    order_type="limit",
                    status=faker.random_element(["open", "inactive"]),
                    price=opened_sell_bit2me_order.price
                    * faker.pyfloat(min_value=0.50, max_value=0.60),
                ),
            ]
            if simulate_pending_buy_orders_to_filled
            else []
        ).model_dump(mode="json", by_alias=True),
    )

    # Mock call to /v1/trading/order to get opened sell orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode(
                {
                    "direction": "desc",
                    "status_in": "open,inactive",
                    "side": "sell",
                    "orderType": "stop-limit",
                },
                doseq=False,
            ),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]]([opened_sell_bit2me_order]).model_dump(
            mode="json", by_alias=True
        ),
    )

    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v2/trading/tickers",
            method="GET",
            query_string={"symbol": opened_sell_bit2me_order.symbol},
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(
        RootModel[list[Bit2MeTickersDto]](
            [
                Bit2MeTickersDtoObjectMother.create(
                    symbol=opened_sell_bit2me_order.symbol,
                    close=(
                        opened_sell_bit2me_order.stop_price
                        + faker.pyfloat(min_value=10.000, max_value=100.000)
                    ),
                )
            ]
        ).model_dump(mode="json", by_alias=True),
    )

    if not simulate_pending_buy_orders_to_filled:
        # Mock call to DELETE /v1/trading/order/{id}
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                f"/bit2me-api/v1/trading/order/{str(opened_sell_bit2me_order.id)}",
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
