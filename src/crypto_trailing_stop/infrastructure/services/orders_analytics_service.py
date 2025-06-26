import logging
from httpx import AsyncClient
from crypto_trailing_stop.commons.constants import (
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import (
    StopLossPercentItem,
)
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import (
    LimitSellOrderGuardMetrics,
)
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import (
    StopLossPercentService,
)
from crypto_trailing_stop.commons.patterns import SingletonMeta

logger = logging.getLogger(__name__)


class OrdersAnalyticsService(metaclass=SingletonMeta):
    def __init__(
        self,
        bit2me_remote_service: Bit2MeRemoteService,
        stop_loss_percent_service: StopLossPercentService,
    ) -> None:
        self._bit2me_remote_service = bit2me_remote_service
        self._stop_loss_percent_service = stop_loss_percent_service

    async def calculate_limit_sell_order_guard_metrics(
        self,
        *,
        symbol: str | None = None,
    ) -> list[LimitSellOrderGuardMetrics]:
        async with await self._bit2me_remote_service.get_http_client() as client:
            opened_limit_sell_orders = (
                await self._bit2me_remote_service.get_pending_sell_orders(
                    order_type="limit", client=client
                )
            )
            ret = []
            for sell_order in opened_limit_sell_orders:
                if (
                    symbol is None
                    or len(symbol) <= 0
                    or sell_order.symbol.lower().startswith(symbol.lower())
                ):
                    avg_buy_price = await self.calculate_correlated_avg_buy_price(
                        sell_order, client=client
                    )
                    (
                        safeguard_stop_price,
                        stop_loss_percent_item,
                    ) = await self.calculate_safeguard_stop_price(
                        sell_order, avg_buy_price
                    )
                    ret.append(
                        LimitSellOrderGuardMetrics(
                            limit_sell_order=sell_order,
                            avg_buy_price=avg_buy_price,
                            stop_loss_percent_value=stop_loss_percent_item.value,
                            safeguard_stop_price=safeguard_stop_price,
                        )
                    )
            return ret

    async def calculate_correlated_avg_buy_price(
        self,
        sell_order: Bit2MeOrderDto,
        *,
        client: AsyncClient | None = None,
    ) -> float:
        last_filled_buy_orders = await self._bit2me_remote_service.get_orders(
            side="buy", status="filled", symbol=sell_order.symbol, client=client
        )
        idx, sum_order_amount = 0, 0.0
        correlated_filled_buy_orders = []
        while sum_order_amount < sell_order.order_amount and idx < len(
            last_filled_buy_orders
        ):
            current_filled_buy_order = last_filled_buy_orders[idx]
            correlated_filled_buy_orders.append(current_filled_buy_order)
            sum_order_amount += current_filled_buy_order.order_amount
            idx += 1
        numerator = sum(
            [o.price * o.order_amount for o in correlated_filled_buy_orders]
        )
        denominator = sum([o.order_amount for o in correlated_filled_buy_orders])
        correlated_avg_buy_price = round(
            numerator / denominator,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                sell_order.symbol,
                DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
            ),
        )
        return correlated_avg_buy_price

    async def calculate_safeguard_stop_price(
        self, sell_order: Bit2MeOrderDto, avg_buy_price: float
    ) -> tuple[float, StopLossPercentItem]:
        (
            stop_loss_percent_item,
            stop_loss_percent_decimal_value,
        ) = await self.find_stop_loss_percent_by_sell_order(sell_order)

        safeguard_stop_price = round(
            avg_buy_price * (1 - stop_loss_percent_decimal_value),
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                sell_order.symbol,
                DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
            ),
        )
        return safeguard_stop_price, stop_loss_percent_item

    async def find_stop_loss_percent_by_sell_order(
        self, sell_order: Bit2MeOrderDto
    ) -> tuple[StopLossPercentItem, float]:
        crypto_currency_symbol = sell_order.symbol.split("/")[0].strip().upper()
        stop_loss_percent_item = (
            await self._stop_loss_percent_service.find_stop_loss_percent_by_symbol(
                symbol=crypto_currency_symbol
            )
        )
        stop_loss_percent_decimal_value = stop_loss_percent_item.value / 100
        logger.info(
            f"Stop Loss Percent for Symbol {crypto_currency_symbol} "
            + f"is setup to '{stop_loss_percent_item.value} %' (Decimal: {stop_loss_percent_decimal_value})..."
        )
        return stop_loss_percent_item, stop_loss_percent_decimal_value
