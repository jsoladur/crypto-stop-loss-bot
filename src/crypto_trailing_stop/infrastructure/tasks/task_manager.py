import logging
from inspect import isclass
from typing import Self

from dependency_injector.containers import Container
from dependency_injector.providers import Singleton

from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self, global_flag_service: GlobalFlagService, tasks_container: Container) -> None:
        self._global_flag_service = global_flag_service
        self._tasks_container = tasks_container
        self._tasks: dict[GlobalFlagTypeEnum, AbstractTaskService] = {}
        self._global_flag_service.set_task_manager(self)

    async def load_tasks(self) -> Self:
        self._tasks.update(self._import_task_modules())
        logger.info("Task classes imported and instantiated! Starting what are needed!")
        for global_flag_type in GlobalFlagTypeEnum:
            is_global_flag_type_enabled = await self._global_flag_service.is_enabled_for(global_flag_type)
            if is_global_flag_type_enabled:
                await self.start(global_flag_type)
            else:
                await self.stop(global_flag_type)
        return self

    async def start(self, global_flag_type: GlobalFlagTypeEnum) -> None:
        if global_flag_type in self._tasks:
            await self._tasks[global_flag_type].start()
            logger.info(f"Task {global_flag_type.value} STARTED!")

    async def stop(self, global_flag_type: GlobalFlagTypeEnum) -> None:
        if global_flag_type in self._tasks:
            await self._tasks[global_flag_type].stop()
            logger.info(f"Task {global_flag_type.value} STOPPED!")

    def get_tasks(self) -> list[AbstractTaskService]:
        return dict(self._tasks)

    def _import_task_modules(self) -> dict[GlobalFlagTypeEnum, AbstractTaskService]:
        ret: dict[GlobalFlagTypeEnum, AbstractTaskService] = {}
        for provider in self._tasks_container.traverse(types=[Singleton]):
            if isclass(provider.provides) and issubclass(provider.provides, AbstractTaskService):
                dependency_object = provider()
                ret[dependency_object.get_global_flag_type()] = dependency_object
        return ret
