import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult

logger = logging.getLogger(__name__)


class MarketSignalService(AbstractService):
    __metaclass__ = SingletonMeta

    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._event_emitter = get_event_emitter()
        self._event_emitter.add_listener("signals_evaluation_result", self.on_signals_evaluation_result)

    async def on_signals_evaluation_result(self, signals: SignalsEvaluationResult) -> None:
        try:
            raise NotImplementedError("")
        except Exception as e:
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)
