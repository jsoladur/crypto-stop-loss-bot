from dataclasses import dataclass

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.order import Order


@dataclass
class LimitSellOrderGuardMetrics:
    sell_order: Order
    current_price: float | int
    avg_buy_price: float | int
    break_even_price: float | int
    current_profit: float | int
    net_revenue: float | int
    # Stop loss and take profit metrics
    stop_loss_percent_value: float
    safeguard_stop_price: float
    # Current metrics that affects to 'suggested' fields
    current_attr_value: float | int
    current_atr_percent: float | int
    closing_price: float | int
    # Suggested and dinamically calculated based on current volatility
    suggested_stop_loss_percent_value: float
    suggested_safeguard_stop_price: float
    suggested_take_profit_percent_value: float
    suggested_take_profit_limit_price: float

    @property
    def profit_factor(self) -> float:
        return round(self.suggested_take_profit_percent_value / self.suggested_stop_loss_percent_value, ndigits=2)
