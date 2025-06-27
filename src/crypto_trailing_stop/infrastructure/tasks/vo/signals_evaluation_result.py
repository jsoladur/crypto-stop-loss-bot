from dataclasses import dataclass
from typing import Literal


@dataclass
class SignalsEvaluationResult:
    buy: bool
    sell: bool
    rsi_state: Literal["neutral", "overbought", "oversold"]
