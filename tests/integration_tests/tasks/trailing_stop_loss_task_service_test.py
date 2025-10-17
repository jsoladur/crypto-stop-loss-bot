import math
from unittest.mock import patch
from urllib.parse import urlencode

import pydash
import pytest
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.commons.constants import DEFAULT_TRAILING_STOP_LOSS_PERCENT
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.tasks.trailing_stop_loss_task_service import TrailingStopLossTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeOrderDtoObjectMother, Bit2MeTickersDtoObjectMother


@pytest.mark.parametrize("simulate_pending_buy_orders_to_filled", [True, False])
@pytest.mark.asyncio
async def should_make_all_expected_calls_to_bit2me_when_trailing_stop_loss(
    faker: Faker, simulate_pending_buy_orders_to_filled: bool, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a trailing stop is loss.
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()

    _prepare_httpserver_mock(
        faker, simulate_pending_buy_orders_to_filled, httpserver, bit2me_api_key, bit2me_api_secret
    )
    trailing_stop_loss_task_service: TrailingStopLossTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.TRAILING_STOP_LOSS
    ]
    with patch.object(
        TrailingStopLossTaskService, "_notify_fatal_error_via_telegram"
    ) as notify_fatal_error_via_telegram_mock:
        await trailing_stop_loss_task_service.run()
        notify_fatal_error_via_telegram_mock.assert_not_called()
        httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker,
    simulate_pending_buy_orders_to_filled: bool,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
) -> None:
    opened_sell_bit2me_order = Bit2MeOrderDtoObjectMother.create(
        side="sell", order_type="stop-limit", status=faker.random_element(["open", "inactive"])
    )
    opened_buy_orders = (
        [
            # Bullish breakout buy order
            Bit2MeOrderDtoObjectMother.create(
                side="buy",
                symbol=opened_sell_bit2me_order.symbol,
                order_type="stop-limit",
                status=faker.random_element(["open", "inactive"]),
                price=opened_sell_bit2me_order.price * round(faker.pyfloat(min_value=1.20, max_value=1.40), ndigits=2),
            ),
            # Min buy order
            Bit2MeOrderDtoObjectMother.create(
                side="buy",
                symbol=opened_sell_bit2me_order.symbol,
                order_type="limit",
                status=faker.random_element(["open", "inactive"]),
                price=opened_sell_bit2me_order.price * round(faker.pyfloat(min_value=0.20, max_value=0.40), ndigits=2),
            ),
            # Middle-ground buy order
            Bit2MeOrderDtoObjectMother.create(
                side="buy",
                symbol=opened_sell_bit2me_order.symbol,
                order_type="limit",
                status=faker.random_element(["open", "inactive"]),
                price=opened_sell_bit2me_order.price * round(faker.pyfloat(min_value=0.75, max_value=0.80), ndigits=2),
            ),
            # Max buy order
            Bit2MeOrderDtoObjectMother.create(
                side="buy",
                symbol=opened_sell_bit2me_order.symbol,
                order_type="limit",
                status=faker.random_element(["open", "inactive"]),
                price=opened_sell_bit2me_order.price * 0.995,
            ),
        ]
        if simulate_pending_buy_orders_to_filled
        else []
    )
    tickers = Bit2MeTickersDtoObjectMother.create(
        symbol=opened_sell_bit2me_order.symbol,
        close=(
            opened_sell_bit2me_order.stop_price
            + (0.5 if simulate_pending_buy_orders_to_filled else faker.pyfloat(min_value=10.000, max_value=100.000))
        ),
    )
    rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=opened_sell_bit2me_order.symbol)
    tickers_list = [tickers] + rest_tickers
    # Mock call to /v1/trading/order to get opened buy orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode({"direction": "desc", "status_in": "open,inactive", "side": "buy"}, doseq=False),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeOrderDto]](opened_buy_orders).model_dump(mode="json", by_alias=True))

    # Mock call to /v1/trading/order to get opened sell orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode(
                {"direction": "desc", "status_in": "open,inactive", "side": "sell", "orderType": "stop-limit"},
                doseq=False,
            ),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]]([opened_sell_bit2me_order]).model_dump(mode="json", by_alias=True)
    )

    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v2/trading/tickers", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeTickersDto]](tickers_list).model_dump(mode="json", by_alias=True))

    lowest_buy_price = math.inf
    if opened_buy_orders:
        highest_opened_buy_order = pydash.max_by(opened_buy_orders, lambda order: order.stop_price or order.price)
        highest_buy_price = highest_opened_buy_order.stop_price or highest_opened_buy_order.price

    if not simulate_pending_buy_orders_to_filled or (
        tickers.close > highest_buy_price
        and ((1 - (lowest_buy_price / tickers.close)) * 100) > DEFAULT_TRAILING_STOP_LOSS_PERCENT
    ):
        # Mock call to DELETE /v1/trading/order/{id}
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                f"/bit2me-api/v1/trading/order/{str(opened_sell_bit2me_order.id)}", method="DELETE"
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_response(Response(status=204))

        # Mock call to POST /v1/trading/order
        httpserver.expect(
            Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/order", method="POST").set_bit2me_api_key_and_secret(
                bit2me_api_key, bik2me_api_secret
            ),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            Bit2MeOrderDtoObjectMother.create(
                side="sell", order_type="stop-limit", status=faker.random_element(["open", "inactive"])
            ).model_dump(by_alias=True, mode="json")
        )
