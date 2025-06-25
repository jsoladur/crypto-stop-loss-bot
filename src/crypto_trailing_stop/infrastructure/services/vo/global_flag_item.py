from dataclasses import dataclass
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum


@dataclass
class GlobalFlagItem:
    name: GlobalFlagTypeEnum
    value: bool
