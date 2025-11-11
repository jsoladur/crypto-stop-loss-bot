from dataclasses import dataclass, field, fields
from typing import Literal, Self

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem

TakeProfitFilter = Literal["all", "enabled", "disabled"]


@dataclass
class ParametersRefinementResult:
    ema_short: int
    ema_mid: int
    buy_min_volume_threshold_values: list[float] = field(default_factory=list)
    buy_max_volume_threshold_values: list[float] = field(default_factory=list)
    sell_min_volume_threshold_values: list[float] = field(default_factory=list)
    sp_tp_tuples: list[tuple[bool, float, float]] = field(default_factory=list)


@dataclass
class BacktestingOutcomes:
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
class BacktestingExecutionResult:
    parameters: BuySellSignalsConfigItem
    outcomes: BacktestingOutcomes


class BacktestingInOutOfSampleExecutionResult(BacktestingExecutionResult):
    out_of_sample_outcomes: BacktestingOutcomes | None = None

    @property
    def in_sample_outcomes(self) -> BacktestingOutcomes:
        return self.outcomes

    @staticmethod
    def from_(result: BacktestingExecutionResult) -> Self:
        """Create an In/Out-of-sample result from a plain BacktestingExecutionResult."""
        kwargs = {f.name: getattr(result, f.name) for f in fields(BacktestingExecutionResult)}
        return BacktestingInOutOfSampleExecutionResult(**kwargs)


@dataclass
class BacktestingInOutOfSampleRanking:
    best_overall: BacktestingInOutOfSampleExecutionResult | None = None
    highest_quality: BacktestingInOutOfSampleExecutionResult | None = None
    best_profitable: BacktestingInOutOfSampleExecutionResult | None = None
    best_win_rate: BacktestingInOutOfSampleExecutionResult | None = None

    @property
    def all(self) -> list[BacktestingInOutOfSampleExecutionResult]:
        return [getattr(self, field.name) for field in fields(self) if getattr(self, field.name) is not None]
