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
    take_profit_percent_value: float
    take_profit_limit_price: float
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

    @property
    def potential_loss_at_sl(self) -> float:
        """
        Calculates the potential loss (in the quote currency) if the
        active safeguard_stop_price is hit.
        """
        loss_per_unit = self.break_even_price - self.safeguard_stop_price
        total_loss = loss_per_unit * self.sell_order.amount
        # Assuming 2 decimal places for fiat, but you could fetch
        # trading_market_config.price_precision if needed.
        return round(total_loss, ndigits=2)

    @property
    def potential_profit_at_tp(self) -> float:
        """
        Calculates the potential profit (in the quote currency) if the
        take_profit_limit_price is hit.
        """
        profit_per_unit = self.take_profit_limit_price - self.break_even_price
        total_profit = profit_per_unit * self.sell_order.amount
        return round(total_profit, ndigits=2)
