from abc import ABC, abstractmethod


class AbstractTaskService(ABC):
    @abstractmethod
    def run(self, *args, **kwargs) -> None:
        """
        Run the task
        """
