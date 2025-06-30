from pydantic import BaseModel


class Bit2MePaginationResultDto[T: BaseModel](BaseModel):
    data: list[T]
    total: int
