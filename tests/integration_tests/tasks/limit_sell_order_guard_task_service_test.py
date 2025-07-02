from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from aiogram import Bot
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.limit_sell_order_guard_task_service import LimitSellOrderGuardTaskService
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    Bit2MeTradeDtoObjectMother,
)


@pytest.mark.asyncio
async def should_create_market_sell_order_when_price_goes_down_applying_guard(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env

    task_manager = get_task_manager_instance()

    _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)

    # Provoke send a notification via Telegram
    push_notification = PushNotification(
        {
            PushNotification.telegram_chat_id: faker.random_number(digits=9, fix_len=True),
            PushNotification.notification_type: PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT,
        }
    )
    await push_notification.save()

    limit_sell_order_guard_task_service: LimitSellOrderGuardTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
    ]
    with patch.object(Bot, "send_message"):
        await limit_sell_order_guard_task_service._run()

    httpserver.check_assertions()


def _prepare_httpserver_mock(faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str) -> None:
    orders_price = faker.pyfloat(positive=True, min_value=500, max_value=1_000)
    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
    opened_sell_bit2me_orders = [
        Bit2MeOrderDtoObjectMother.create(
            side="sell",
            symbol=symbol,
            order_type="stop-limit",
            price=orders_price,
            status=faker.random_element(["open", "inactive"]),
        ),
        Bit2MeOrderDtoObjectMother.create(
            side="sell",
            symbol=symbol,
            order_type="limit",
            price=orders_price,
            status=faker.random_element(["open", "inactive"]),
        ),
    ]
    tickers = Bit2MeTickersDtoObjectMother.create(symbol=symbol, close=orders_price * 0.2)
    buy_trades = _generate_trades(faker, opened_sell_bit2me_orders)
    # Mock call to /v1/trading/order to get opened sell orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode({"direction": "desc", "status_in": "open,inactive", "side": "sell"}, doseq=False),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]](opened_sell_bit2me_orders).model_dump(mode="json", by_alias=True)
    )
    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v2/trading/tickers", method="GET", query_string={"symbol": symbol}
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeTickersDto]]([tickers]).model_dump(mode="json", by_alias=True))

    for sell_order in opened_sell_bit2me_orders:
        # Mock call to /v1/trading/trade to get closed buy trades
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/trade",
                method="GET",
                query_string=urlencode({"direction": "desc", "side": "buy", "symbol": symbol}, doseq=False),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_response(Response(status=403))
        # Mock trades /v1/trading/trade
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/trade",
                method="GET",
                query_string=urlencode({"direction": "desc", "side": "buy", "symbol": symbol}, doseq=False),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            Bit2MePaginationResultDto[Bit2MeTradeDto](
                data=buy_trades, total=faker.pyint(min_value=len(buy_trades), max_value=len(buy_trades) * 10)
            ).model_dump(mode="json", by_alias=True)
        )
        # Mock call to DELETE /v1/trading/order/{id}
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                f"/bit2me-api/v1/trading/order/{str(sell_order.id)}", method="DELETE"
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
                side="sell", order_type="market", status=faker.random_element(["open", "inactive"])
            ).model_dump(by_alias=True, mode="json")
        )


def _generate_trades(faker: Faker, opened_sell_bit2me_orders: list[Bit2MeOrderDto]) -> list[Bit2MeTradeDto]:
    buy_trades = []
    for sell_order in opened_sell_bit2me_orders:
        number_of_trades = faker.random_element([2, 4])
        for _ in range(number_of_trades):
            buy_trades.append(
                Bit2MeTradeDtoObjectMother.create(
                    side="buy",
                    symbol=sell_order.symbol,
                    price=sell_order.price * 0.5,
                    amount=sell_order.order_amount / number_of_trades,
                )
            )

    return buy_trades
