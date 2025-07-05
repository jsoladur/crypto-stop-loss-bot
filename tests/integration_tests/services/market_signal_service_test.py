import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.commons.constants import SIGNALS_EVALUATION_RESULT_EVENT_NAME
from crypto_trailing_stop.config import get_event_emitter
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from tests.helpers.object_mothers import SignalsEvaluationResultObjectMother

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_save_market_signals_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env
    market_signal_service = MarketSignalService()
    event_emitter = get_event_emitter()

    # 1. Saving 1h before any 4h signal are ignored!
    one_hour_signals = SignalsEvaluationResultObjectMother.list(timeframe="1h")
    signal, *_ = one_hour_signals
    symbol = signal.symbol

    for current in one_hour_signals:
        event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, current)
        await asyncio.sleep(delay=2.0)

    symbols = await market_signal_service.find_all_symbols()
    assert len(symbols) <= 0
    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) <= 0

    # 2. Saving 4h signal and then 1h later on, it works!
    four_hour_signal = SignalsEvaluationResultObjectMother.create(
        timestamp=datetime.now(UTC) + timedelta(days=-10), timeframe="4h", symbol=symbol
    )
    event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, four_hour_signal)
    await asyncio.sleep(delay=2.0)
    for current in one_hour_signals:
        event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, current)
        await asyncio.sleep(delay=2.0)

    await asyncio.sleep(delay=5.0)

    symbols = await market_signal_service.find_all_symbols()
    assert len(symbols) == 1
    assert symbol in symbols

    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) >= len(one_hour_signals)
    first_returned_signal, *_ = market_signals

    _assert_with(four_hour_signal, first_returned_signal)

    market_signals_for_1h = await market_signal_service.find_by_symbol(symbol, timeframe="1h")
    assert len(market_signals_for_1h) == len(one_hour_signals)

    # 3. Creating a new market signal for 4h, all 1h hour are deleted
    new_four_hour_signal = SignalsEvaluationResultObjectMother.create(
        timestamp=datetime.now(UTC) + timedelta(days=-10), timeframe="4h", symbol=symbol
    )
    event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, new_four_hour_signal)
    await asyncio.sleep(delay=5.0)

    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) == 1

    market_signals_for_1h = await market_signal_service.find_by_symbol(symbol, timeframe="1h")
    assert len(market_signals_for_1h) <= 0


def _assert_with(expected: SignalsEvaluationResult, returned: MarketSignalItem) -> None:
    assert expected.symbol == returned.symbol
    assert expected.timeframe == returned.timeframe
    assert returned.signal_type == ("buy" if expected.buy else "sell")
