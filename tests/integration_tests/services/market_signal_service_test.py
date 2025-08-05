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


@pytest.mark.parametrize("use_event_emitter", [False, True])
@pytest.mark.asyncio
async def should_save_market_signals_properly_when_invoke_to_service(
    faker: Faker, use_event_emitter: bool, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env
    market_signal_service = MarketSignalService()

    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
    one_hour_signals = SignalsEvaluationResultObjectMother.list(timeframe="1h", symbol=symbol)
    half_hour_signals = SignalsEvaluationResultObjectMother.list(timeframe="30m", symbol=symbol)
    for current in one_hour_signals:
        await _invoke_on_signals_evaluation_result(market_signal_service, current, use_event_emitter=use_event_emitter)
    # 2. 30m signals are ignored
    for current in half_hour_signals:
        await _invoke_on_signals_evaluation_result(market_signal_service, current, use_event_emitter=use_event_emitter)

    symbols = await market_signal_service.find_all_symbols()
    assert len(symbols) >= 1
    assert symbol in symbols

    total_expected_1h_signals = sum(
        [2 if one_hour_signal.is_divergence_signal else 1 for one_hour_signal in one_hour_signals]
    )

    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) == total_expected_1h_signals

    # 2. Saving 4h signal and then 1h later on, it works!
    first_four_hour_signal = SignalsEvaluationResultObjectMother.create(
        timestamp=datetime.now(UTC) + timedelta(days=-10), timeframe="4h", symbol=symbol
    )
    await _invoke_on_signals_evaluation_result(
        market_signal_service, first_four_hour_signal, use_event_emitter=use_event_emitter
    )
    for current in one_hour_signals:
        await _invoke_on_signals_evaluation_result(market_signal_service, current, use_event_emitter=use_event_emitter)
    for current in half_hour_signals:
        await _invoke_on_signals_evaluation_result(market_signal_service, current, use_event_emitter=use_event_emitter)

    symbols = await market_signal_service.find_all_symbols()
    assert len(symbols) >= 1
    assert symbol in symbols

    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) == ((total_expected_1h_signals * 2) + 1)

    all_four_hour_signals = [market_signal for market_signal in market_signals if market_signal.timeframe == "4h"]
    assert len(all_four_hour_signals) == 1
    first_4h_returned_signal, *_ = all_four_hour_signals
    _assert_with(first_four_hour_signal, first_4h_returned_signal)

    market_signals_for_1h = await market_signal_service.find_by_symbol(symbol, timeframe="1h")
    assert len(market_signals_for_1h) == (total_expected_1h_signals * 2)

    market_signals_for_4h = await market_signal_service.find_by_symbol(symbol, timeframe="4h")
    assert len(market_signals_for_4h) == 1

    market_signals_for_30m = await market_signal_service.find_by_symbol(symbol, timeframe="30m")
    assert len(market_signals_for_30m) <= 0

    # 3. 4h signals in the same trend is ignored
    await asyncio.sleep(delay=2.0)

    new_four_hour_signal_same_trend = SignalsEvaluationResultObjectMother.create(
        timestamp=datetime.now(UTC) + timedelta(days=-10), timeframe="4h", symbol=symbol, buy=first_four_hour_signal.buy
    )
    await _invoke_on_signals_evaluation_result(
        market_signal_service, new_four_hour_signal_same_trend, use_event_emitter=use_event_emitter
    )

    market_signals_for_4h = await market_signal_service.find_by_symbol(symbol, timeframe="4h")

    second_4h_returned_signal, *_ = market_signals_for_4h

    assert first_4h_returned_signal.timestamp == second_4h_returned_signal.timestamp

    _assert_with(first_four_hour_signal, first_4h_returned_signal)

    market_signals_for_1h = await market_signal_service.find_by_symbol(symbol, timeframe="1h")
    assert len(market_signals_for_1h) == (total_expected_1h_signals * 2)

    market_signals_for_30m = await market_signal_service.find_by_symbol(symbol, timeframe="30m")
    assert len(market_signals_for_30m) <= 0

    # 4. Creating a new market signal for 4h, which switches market in the against direction, so then
    # all 1h hour should be deleted
    await asyncio.sleep(delay=2.0)

    new_four_hour_signal_against_trend = SignalsEvaluationResultObjectMother.create(
        timestamp=datetime.now(UTC), timeframe="4h", symbol=symbol, buy=not first_four_hour_signal.buy
    )
    await _invoke_on_signals_evaluation_result(
        market_signal_service, new_four_hour_signal_against_trend, use_event_emitter=use_event_emitter
    )

    market_signals = await market_signal_service.find_by_symbol(symbol)
    assert len(market_signals) >= 1

    market_signals_for_1h = await market_signal_service.find_by_symbol(symbol, timeframe="1h")
    assert len(market_signals_for_1h) <= (total_expected_1h_signals * 2)

    market_signals_for_4h = await market_signal_service.find_by_symbol(symbol, timeframe="4h")

    final_4h_returned_signal, *_ = market_signals_for_4h

    assert first_4h_returned_signal.timestamp < final_4h_returned_signal.timestamp


async def _invoke_on_signals_evaluation_result(
    market_signal_service: MarketSignalService, signals: SignalsEvaluationResult, *, use_event_emitter: bool
) -> None:
    if use_event_emitter:
        event_emitter = get_event_emitter()
        event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, signals)
        await asyncio.sleep(delay=1.0)
    else:
        await market_signal_service.on_signals_evaluation_result(signals)


def _assert_with(expected: SignalsEvaluationResult, returned: MarketSignalItem) -> None:
    assert expected.symbol == returned.symbol
    assert expected.timeframe == returned.timeframe
    assert returned.signal_type == ("buy" if expected.buy else "sell")
