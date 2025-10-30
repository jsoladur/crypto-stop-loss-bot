from dataclasses import dataclass
from typing import Literal

PositionType = Literal["Long", "Short"]


@dataclass(frozen=True)
class LeveragedPositionHits:
    position_type: PositionType
    entry_price: float  # Entry price (Ask for Long, Bid for Short)
    stop_loss_price: float  # Technical Stop-Loss price
    take_profit_price: float  # Technical Take-Profit price
    # Capital Metrics
    required_margin_eur: float  # Amount to post as margin
    position_size_eur: float  # Total Notional Size of the position
    # Risk Metrics
    loss_at_stop_loss_eur: float  # Real loss in EUR if the SL is hit
    risk_as_percent_of_total_capital: float  # The % of your total capital you are risking
    # Liquidation Metrics
    liquidation_price: float  # Estimated liquidation price
    is_safe_from_liquidation: bool  # True if your SL will trigger BEFORE liquidation


@dataclass(frozen=True)
class TradeNowHints:
    symbol: str
    leverage_value: int
    # Technical Parameters
    stop_loss_percent_value: float
    take_profit_percent_value: float
    profit_factor: float
    # Position Calculations
    long: LeveragedPositionHits
    short: LeveragedPositionHits
