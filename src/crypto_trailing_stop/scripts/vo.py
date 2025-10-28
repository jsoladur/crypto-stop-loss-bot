from dataclasses import dataclass, field, fields
from typing import Literal

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem

TakeProfitFilter = Literal["all", "enabled", "disabled"]


@dataclass
class ParametersRefinementResult:
    ema_short: int
    ema_mid: int
    buy_min_volume_threshold_values: list[float] = field(default_factory=list)
    buy_max_volume_threshold_values: list[float] = field(default_factory=list)
    sell_min_volume_threshold_values: list[float] = field(default_factory=list)


@dataclass
class BacktestingExecutionResult:
    parameters: BuySellSignalsConfigItem
    # Important metrics
    number_of_trades: int
    win_rate: float
    net_profit_amount: float
    net_profit_percentage: float
    # Metadata
    avg_trade_duration_in_days: float
    max_trade_duration_in_days: float
    buy_and_hold_return_percentage: float
    profit_factor: float
    best_trade_percentage: float
    worst_trade_percentage: float
    avg_drawdown_percentage: float
    max_drawdown_percentage: float
    avg_drawdown_duration_in_days: float
    max_drawdown_duration_in_days: float
    sqn: float


@dataclass
class BacktestingExecutionSummary:
    best_overall: BacktestingExecutionResult | None = None
    highest_quality: BacktestingExecutionResult | None = None
    best_profitable: BacktestingExecutionResult | None = None
    best_win_rate: BacktestingExecutionResult | None = None

    @property
    def all(self) -> list[BacktestingExecutionResult]:
        return [getattr(self, field.name) for field in fields(self) if getattr(self, field.name) is not None]


__all__ = ["BacktestingExecutionResult", "BacktestingExecutionSummary", "TakeProfitFilter"]
