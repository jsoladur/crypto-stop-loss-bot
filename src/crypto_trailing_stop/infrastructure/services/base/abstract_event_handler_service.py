import logging
from abc import ABCMeta, abstractmethod

from crypto_trailing_stop.infrastructure.services.base.abstract_service import AbstractService

logger = logging.getLogger(__name__)


class AbstractEventHandlerService(AbstractService, metaclass=ABCMeta):
    @abstractmethod
    def configure(self) -> None:
        """
        Configure event emitter handler
        """
