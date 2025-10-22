from urllib.parse import urlencode

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import MEXCOrderDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher, MEXCAPIRequestMatcher
from tests.helpers.object_mothers import Bit2MeOrderDtoObjectMother, MEXCOrderDtoObjectMother


def prepare_httpserver_open_sell_orders_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    *,
    opened_sell_orders: list[Bit2MeOrderDto] | list[MEXCOrderDto] = None,
) -> list[Bit2MeOrderDto] | list[MEXCOrderDto]:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            opened_sell_orders = opened_sell_orders or [
                Bit2MeOrderDtoObjectMother.create(
                    side="sell",
                    order_type="stop-limit",
                    symbol=symbol,
                    status=faker.random_element(["open", "inactive"]),
                ),
                Bit2MeOrderDtoObjectMother.create(
                    side="sell", order_type="limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
                ),
            ]
            # Mock call to /v1/trading/order to get opened sell orders
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    "/bit2me-api/v1/trading/order",
                    method="GET",
                    query_string=urlencode(
                        {"direction": "desc", "status_in": "open,inactive", "side": "sell"}, doseq=False
                    ),
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[Bit2MeOrderDto]](opened_sell_orders).model_dump(mode="json", by_alias=True)
            )
        case OperatingExchangeEnum.MEXC:
            opened_sell_orders = opened_sell_orders or [
                MEXCOrderDtoObjectMother.create(side="SELL", symbol=symbol, order_type="STOP_LIMIT", status="NEW"),
                MEXCOrderDtoObjectMother.create(side="SELL", symbol=symbol, order_type="LIMIT", status="NEW"),
            ]
            httpserver.expect(
                MEXCAPIRequestMatcher("/mexc-api/api/v3/openOrders", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[MEXCOrderDto]](opened_sell_orders).model_dump(mode="json", by_alias=True)
            )

    return opened_sell_orders


def prepare_httpserver_delete_order_mock(
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    open_sell_order: Bit2MeOrderDto | MEXCOrderDto,
) -> None:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    f"/bit2me-api/v1/trading/order/{str(open_sell_order.id)}", method="DELETE"
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_response(Response(status=204))
        case OperatingExchangeEnum.MEXC:
            MEXCAPIRequestMatcher, CustomAPIQueryMatcher
            httpserver.expect(
                MEXCAPIRequestMatcher(
                    "/mexc-api/api/v3/order",
                    query_string=CustomAPIQueryMatcher(
                        {"symbol": open_sell_order.symbol, "orderId": str(open_sell_order.order_id)},
                        additional_required_query_params=["signature", "timestamp"],
                    ),
                    method="DELETE",
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                open_sell_order.model_copy(update={"status": "CANCELED"}, deep=True).model_dump(
                    by_alias=True, mode="json"
                )
            )
