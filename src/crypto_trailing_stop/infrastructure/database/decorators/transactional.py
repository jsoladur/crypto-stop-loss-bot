from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from piccolo.engine.base import Engine

from crypto_trailing_stop.infrastructure.database.engine import get_engine


def transactional(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Awaitable[Any]:
        engine: Engine = get_engine()
        async with engine.transaction():
            return await func(*args, **kwargs)

    return wrapper
