import logging

from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.database.decorators import transactional
from crypto_trailing_stop.infrastructure.database.models import MarketSignal
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult

logger = logging.getLogger(__name__)


class MarketSignalService(AbstractService, metaclass=SingletonABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()

    def configure(self) -> None:
        get_event_emitter().add_listener("signals_evaluation_result", self.on_signals_evaluation_result)

    async def on_signals_evaluation_result(self, signals: SignalsEvaluationResult) -> None:
        try:
            if signals.is_positive:
                await self._store_signals(signals)
            else:
                logger.debug("There are no signals to store!")
        except Exception as e:
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    @transactional
    async def _store_signals(self, signals: SignalsEvaluationResult) -> None:
        match signals.timeframe:
            case "4h":
                await self._store_4h_signals(signals)
            case "1h":
                await self._store_1h_signals(signals)
            case _:
                logger.info(f"There is no enough reability to store the timeframe {signals.timeframe}")
        raise NotImplementedError("To be implemented!")

    async def _store_4h_signals(self, signals: SignalsEvaluationResult) -> None:
        # 1.) Delete all signals for the symbol,
        # since a new 4h market sentiment switcher has appeared
        await MarketSignal.delete().where(MarketSignal.symbol == signals.symbol)
        new_market_signal = MarketSignal(
            symbol=signals.symbol, timeframe=signals.timeframe, signal_type="buy" if signals.buy else "sell"
        )
        await new_market_signal.save()

    async def _store_1h_signals(self, signals: SignalsEvaluationResult) -> None:
        count = (
            await MarketSignal.count()
            .where(MarketSignal.symbol == signals.symbol)
            .where(MarketSignal.timeframe == "4h")
        )
        # If there is no 4h signal previously stored,
        # any 1h signal is ignored, since we do not know what the market sentiment is!
        if count > 0:
            raise NotImplementedError("To be implemented!")
