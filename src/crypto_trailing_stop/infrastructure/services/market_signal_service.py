import logging
from datetime import UTC, datetime, timedelta
from typing import override

from crypto_trailing_stop.commons.constants import SIGNALS_EVALUATION_RESULT_EVENT_NAME, TRIGGER_BUY_ACTION_EVENT_NAME
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.database.models.market_signal import MarketSignal
from crypto_trailing_stop.infrastructure.services.base import AbstractEventHandlerService
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class MarketSignalService(AbstractEventHandlerService, metaclass=SingletonABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()

    @override
    def configure(self) -> None:
        event_emitter = get_event_emitter()
        event_emitter.add_listener(SIGNALS_EVALUATION_RESULT_EVENT_NAME, self.on_signals_evaluation_result)

    async def find_by_symbol(
        self, symbol: str, *, timeframe: Timeframe | None = None, ascending: bool = True
    ) -> list[MarketSignalItem]:
        query = MarketSignal.objects().where(MarketSignal.symbol == symbol)
        if timeframe:
            query = query.where(MarketSignal.timeframe == timeframe)
        market_signals = await query.order_by(MarketSignal.timestamp, ascending=ascending)
        ret = [self._convert_model_to_vo(market_signal) for market_signal in market_signals]
        return ret

    async def find_last_market_signal(self, symbol: str, *, timeframe: Timeframe = "1h") -> MarketSignalItem | None:
        last_market_signal: MarketSignal | None = (
            await MarketSignal.objects()
            .where(MarketSignal.symbol == symbol)
            .where(MarketSignal.timeframe == timeframe)
            .order_by(MarketSignal.timestamp, ascending=False)
            .first()
        )
        ret: MarketSignalItem | None = None
        if last_market_signal:
            ret = self._convert_model_to_vo(last_market_signal)
        return ret

    async def find_all_symbols(self) -> list[str]:
        query_result = await MarketSignal.select(MarketSignal.symbol).distinct()
        ret = [current["symbol"] for current in query_result]
        return ret

    async def on_signals_evaluation_result(self, signals: SignalsEvaluationResult) -> None:
        try:
            if signals.is_positive:
                await self._store_signals(signals)
            else:  # pragma: no cover
                logger.debug("There are no signals to store!")
        except Exception as e:  # pragma: no cover
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    async def _store_signals(self, signals: SignalsEvaluationResult) -> None:
        match signals.timeframe:
            case "4h":
                await self._store_4h_signals(signals)
            case "1h":
                await self._store_1h_signals(signals)
            case _:
                logger.info(f"There is no enough reability to store the timeframe {signals.timeframe}")

    async def _store_4h_signals(self, signals: SignalsEvaluationResult) -> None:
        # NOTE: It only stores buy sell signals for 4h timeframe.
        #       For now, we are not going to store divergence signals.
        if signals.is_buy_sell_signal:
            count = (
                await MarketSignal.count()
                .where(MarketSignal.symbol == signals.symbol)
                .where(MarketSignal.timeframe == signals.timeframe)
                .where(MarketSignal.signal_type == ("buy" if signals.buy else "sell"))
            )
            # Store new 4h signal if the market switches from bullish to bearish or viceversa.
            # Same trend does not make any effect
            if count <= 0:
                # 1.) Delete all 4h signals for the symbol, since we only need the last one
                # if it is a market switcher
                await (
                    MarketSignal.delete()
                    .where(MarketSignal.symbol == signals.symbol)
                    .where(MarketSignal.timeframe == signals.timeframe)
                )
                # 2.) Save the new one
                await self._save_new_market_signals(signals)
        elif signals.is_divergence_signal:  # pragma: no cover
            logger.debug("Divergence signals for 4h timeframe are ignored for now!")

    async def _store_1h_signals(self, signals: SignalsEvaluationResult) -> None:
        new_market_signals = await self._save_new_market_signals(signals)
        for new_market_signal in new_market_signals:
            if new_market_signal.is_candidate_to_trigger_buy_action:
                event_emitter = get_event_emitter()
                event_emitter.emit(TRIGGER_BUY_ACTION_EVENT_NAME, new_market_signal)

    async def _save_new_market_signals(self, signals: SignalsEvaluationResult) -> list[MarketSignalItem]:
        if signals.timeframe != "4h":
            await self._apply_market_signal_retention_policy(signals)
        ret = []
        market_signal_common_args = dict(
            symbol=signals.symbol,
            timeframe=signals.timeframe,
            rsi_state=signals.rsi_state,
            atr=signals.atr,
            closing_price=signals.closing_price,
            ema_long_price=signals.ema_long_price,
        )
        if signals.is_buy_sell_signal:
            buy_sell_market_signal = MarketSignal(
                signal_type="buy" if signals.buy else "sell", **market_signal_common_args
            )
            await buy_sell_market_signal.save()
            ret.append(self._convert_model_to_vo(buy_sell_market_signal))
        if signals.is_divergence_signal:
            divergence_market_signal = MarketSignal(
                signal_type="bearish_divergence" if signals.bearish_divergence else "bullish_divergence",
                **market_signal_common_args,
            )
            await divergence_market_signal.save()
            ret.append(self._convert_model_to_vo(divergence_market_signal))
        return ret

    async def _apply_market_signal_retention_policy(self, signals: SignalsEvaluationResult) -> None:
        expiration_date = datetime.now(tz=UTC) - timedelta(
            days=self._configuration_properties.market_signal_retention_days
        )
        await (
            MarketSignal.delete()
            .where(MarketSignal.symbol == signals.symbol)
            .where(MarketSignal.timeframe == signals.timeframe)
            .where(MarketSignal.timestamp < expiration_date)
        )

    def _convert_model_to_vo(self, market_signal: MarketSignal) -> MarketSignalItem:
        ret = MarketSignalItem(
            timestamp=market_signal.timestamp,
            symbol=market_signal.symbol,
            timeframe=market_signal.timeframe,
            signal_type=market_signal.signal_type,
            rsi_state=market_signal.rsi_state,
            atr=market_signal.atr,
            closing_price=market_signal.closing_price,
            ema_long_price=market_signal.ema_long_price,
        )
        return ret
