import logging
from datetime import UTC, datetime, timedelta

from crypto_trailing_stop.commons.constants import SIGNALS_EVALUATION_RESULT_EVENT_NAME
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.database.models import MarketSignal
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from crypto_trailing_stop.infrastructure.tasks.vo.types import ReliableTimeframe

logger = logging.getLogger(__name__)


class MarketSignalService(AbstractService, metaclass=SingletonABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()

    def configure(self) -> None:
        get_event_emitter().add_listener(SIGNALS_EVALUATION_RESULT_EVENT_NAME, self.on_signals_evaluation_result)

    async def find_by_symbol(
        self, symbol: str, *, timeframe: ReliableTimeframe | None = None, ascending: bool = True
    ) -> list[MarketSignalItem]:
        query = MarketSignal.objects().where(MarketSignal.symbol == symbol)
        if timeframe:
            query = query.where(MarketSignal.timeframe == timeframe)
        market_signals = await query.order_by(MarketSignal.timestamp, ascending=ascending)
        ret = [
            MarketSignalItem(
                timestamp=market_signal.timestamp,
                symbol=market_signal.symbol,
                timeframe=market_signal.timeframe,
                signal_type=market_signal.signal_type,
                rsi_state=market_signal.rsi_state,
                atr=market_signal.atr,
                closing_price=market_signal.closing_price,
                ema_long_price=market_signal.ema_long_price,
            )
            for market_signal in market_signals
        ]
        return ret

    async def find_all_symbols(self) -> list[str]:
        query_result = await MarketSignal.select(MarketSignal.symbol).distinct()
        ret = [current["symbol"] for current in query_result]
        return ret

    async def on_signals_evaluation_result(self, signals: SignalsEvaluationResult) -> None:
        try:
            if signals.is_positive:
                await self._store_signals(signals)
            else:
                logger.debug("There are no signals to store!")
        except Exception as e:
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
            await self._save_new_market_signal(signals)

    async def _store_1h_signals(self, signals: SignalsEvaluationResult) -> None:
        await self._save_new_market_signal(signals)

    async def _save_new_market_signal(self, signals: SignalsEvaluationResult) -> MarketSignal:
        if signals.timeframe != "4h":
            await self._apply_market_signal_retention_policy(signals)
        new_market_signal = MarketSignal(
            symbol=signals.symbol,
            timeframe=signals.timeframe,
            signal_type="buy" if signals.buy else "sell",
            rsi_state=signals.rsi_state,
            atr=signals.atr,
            closing_price=signals.closing_price,
            ema_long_price=signals.ema_long_price,
        )
        await new_market_signal.save()
        return new_market_signal

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
