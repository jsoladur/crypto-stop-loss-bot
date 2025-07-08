from dataclasses import dataclass

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto


@dataclass
class LimitSellOrderGuardMetrics:
    sell_order: Bit2MeOrderDto
    avg_buy_price: float | int
    break_even_price: float | int
    # Fixed by myself
    stop_loss_percent_value: float
    safeguard_stop_price: float | int
    # Suggested and dinamically calculated based on current volatility
    current_attr_value: float | int
    closing_price: float | int
    suggested_stop_loss_percent_value: float
    suggested_safeguard_stop_price: float
    suggested_take_profit_limit_price: float

    @property
    def current_atr_percent(self) -> float:
        return round(
            (self.current_attr_value / self.closing_price) * 100,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                self.sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
            ),
        )
