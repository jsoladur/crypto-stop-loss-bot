from pydantic import BaseModel


class MEXCContractResponseDto[T: BaseModel](BaseModel):
    success: bool = False
    code: int = 0
    data: T
