from datetime import UTC, datetime, timedelta
from typing import Literal, get_args

from faker import Faker

from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe


class SignalsEvaluationResultObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def list(cls, symbol: str | None = None, timeframe: Timeframe | None = None) -> list[SignalsEvaluationResult]:
        now = datetime.now(UTC)
        symbol = symbol or cls._faker.random_element(["ETH/EUR", "SOL/EUR"])
        timeframe = timeframe or cls._faker.random_element(list(get_args(Timeframe)))
        ret = [
            cls.create(timestamp=now + timedelta(days=delta), symbol=symbol, timeframe=timeframe)
            for delta in range(-2, 0)
        ]
        return ret

    @classmethod
    def create(
        cls,
        *,
        timestamp: datetime | None = None,
        symbol: str | None = None,
        timeframe: Timeframe | None = None,
        buy: bool | None = None,
        sell: bool | None = None,
        rsi_state: Literal["neutral", "overbought", "oversold"] | None = None,
        is_choppy: bool | None = None,
    ) -> SignalsEvaluationResult:
        is_choppy = bool(is_choppy) if is_choppy is not None else False
        if not is_choppy:
            buy = bool(buy) if buy is not None else cls._faker.pybool()
        else:
            buy = False
        return SignalsEvaluationResult(
            timestamp=timestamp or datetime.now(UTC),
            symbol=symbol or cls._faker.random_element(["ETH/EUR", "SOL/EUR"]),
            timeframe=timeframe or cls._faker.random_element(list(get_args(Timeframe))),
            buy=buy,
            sell=bool(sell) if sell is not None else not buy,
            rsi_state=rsi_state if rsi_state is not None else "neutral",
            is_choppy=is_choppy,
        )
