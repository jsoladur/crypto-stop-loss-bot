from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class AccountInfo:
    registration_date: datetime | None = None
    currency_code: str
