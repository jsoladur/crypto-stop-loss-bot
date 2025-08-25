from dataclasses import dataclass

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem


@dataclass
class BacktestingExecutionResult:
    parameters: BuySellSignalsConfigItem
    number_of_trades: int
    win_rate: float
    net_profit_amount: float
    net_profit_percentage: float


@dataclass
class BacktestingExecutionSummary:
    best_overall: BacktestingExecutionResult | None = None
    highest_quality: BacktestingExecutionResult | None = None
    best_profitable: BacktestingExecutionResult | None = None
    best_win_rate: BacktestingExecutionResult | None = None
