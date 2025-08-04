from datetime import UTC, datetime, timedelta
from typing import get_args

from faker import Faker

from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState, Timeframe


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
        rsi_state: RSIState | None = None,
        is_choppy: bool | None = None,
        closing_price: float | None = None,
        bearish_divergence: bool = False,
        bullish_divergence: bool = False,
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
            atr=round(cls._faker.pyfloat(min_value=15.0, max_value=30.0), ndigits=2),
            closing_price=closing_price or round(cls._faker.pyfloat(min_value=3_000, max_value=5_000), ndigits=2),
            ema_long_price=round(cls._faker.pyfloat(min_value=1_000, max_value=2_000), ndigits=2),
            bearish_divergence=bearish_divergence,
            bullish_divergence=bullish_divergence,
        )
