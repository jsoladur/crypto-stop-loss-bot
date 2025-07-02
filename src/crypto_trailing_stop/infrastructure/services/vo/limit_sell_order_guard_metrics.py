from dataclasses import dataclass

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto


@dataclass
class LimitSellOrderGuardMetrics:
    sell_order: Bit2MeOrderDto
    stop_loss_percent_value: float
    avg_buy_price: float | int
    safeguard_stop_price: float | int
