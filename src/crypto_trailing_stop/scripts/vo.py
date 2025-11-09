from dataclasses import dataclass, fields
from typing import Literal

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem

TakeProfitFilter = Literal["all", "enabled", "disabled"]


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


@dataclass
class BacktestingInOutOfSampleRanking:
    best_overall: BacktestingInOutOfSampleExecutionResult | None = None
    highest_quality: BacktestingInOutOfSampleExecutionResult | None = None
    best_profitable: BacktestingInOutOfSampleExecutionResult | None = None
    best_win_rate: BacktestingInOutOfSampleExecutionResult | None = None

    @property
    def all(self) -> list[BacktestingExecutionResult]:
        return [getattr(self, field.name) for field in fields(self) if getattr(self, field.name) is not None]
