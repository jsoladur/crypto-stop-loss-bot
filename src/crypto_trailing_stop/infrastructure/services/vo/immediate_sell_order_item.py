from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImmediateSellOrderItem:
    sell_order_id: str
    percent_to_sell: float = field(compare=False, default=100.0)

    def __post_init__(self):
        if self.percent_to_sell < 0.0 or self.percent_to_sell > 100.0:
            raise ValueError("percent_to_sell must be a value between 0.0 and 100.0")
