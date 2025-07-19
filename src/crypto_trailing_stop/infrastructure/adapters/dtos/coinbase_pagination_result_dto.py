from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

class CoinbasePaginationResultDto(BaseModel, Generic[T]):
    data: list[T]
    has_next: bool
    cursor: Optional[str] = None
    size: int