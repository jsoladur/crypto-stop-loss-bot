from dataclasses import dataclass, field


@dataclass
class GlobalSummary:
    """
    Represents a global summary of Bit2Me cryptocurrency data.
    """

    total_deposits: float = field(default=0.0)
    withdrawls: float = field(default=0.0)
    current_value: float = field(default=0.0)
