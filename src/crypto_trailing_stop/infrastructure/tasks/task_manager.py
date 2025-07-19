import logging
from importlib import import_module
from os import listdir, path
from pathlib import Path
from types import ModuleType

from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService, AbstractTradingTaskService

logger = logging.getLogger(__name__)


class _TaskManager:
    def __init__(self):
        self._global_flag_service = GlobalFlagService()
        self._tasks: dict[GlobalFlagTypeEnum, AbstractTaskService] = {}

    async def load_tasks(self) -> "_TaskManager":
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

    def _import_task_modules(self, *, deeply: bool = True) -> dict[GlobalFlagTypeEnum, AbstractTaskService]:
        tasks = {}
        modules = self._import_modules_by_dir(
            dir_to_imported=path.dirname(__file__), package=__package__, deeply=deeply
        )
        for module in modules:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, AbstractTaskService)
                    and attr not in [AbstractTaskService, AbstractTradingTaskService]
                ):
                    logger.info(f"Loading {attr.__name__}...")
                    task_clazz_instance = attr()
                    global_flag_type = task_clazz_instance.get_global_flag_type()
                    if global_flag_type in tasks:
                        raise ValueError("Duplicated task type!")
                    tasks[global_flag_type] = task_clazz_instance
                    logger.info(f"{attr.__name__} has been loaded successfully...")
        return tasks

    def _import_modules_by_dir(self, dir_to_imported: str, package: str, *, deeply: bool = False) -> list[ModuleType]:
        """
        Utility function that allows a simple way to load modules, given the root directory
        in order to seek Python files and import all of them. Keep in mind, this function is
        going to load modules, even though some of them was previously imported

        Args:
            dir_to_imported (str): Root directory path
            package (str): related to the package is related to the above directory.
            deeply (bool, optional): _description_. Defaults to False.

        Returns:
            List[ModuleType]: List of modules, which has been imported sucessfully.
        """
        imported_modules = []
        dir_to_imported = path.realpath(dir_to_imported)
        filter_files_in_dir = list(
            filter(
                lambda f: self._is_scan_candidate_file_to_import(f, deeply),
                map(lambda f: Path(path.realpath(path.join(dir_to_imported, f))), listdir(dir_to_imported)),
            )
        )
        for file_path in filter_files_in_dir:
            if file_path.is_dir():
                imported_modules.extend(
                    self._import_modules_by_dir(
                        dir_to_imported=path.realpath(file_path), package=f"{package}.{file_path.stem}", deeply=deeply
                    )
                )
            else:
                logger.info(f"Importing modules from {file_path.name}...")
                imported_modules.append(import_module(f".{file_path.stem}", package=package))
                logger.debug(f"Modules has been imported from {file_path.name} has been loaded successfully...")
        return imported_modules

    def _is_scan_candidate_file_to_import(self, file_path: Path, deeply: bool = False) -> bool:
        if file_path.is_file():
            if file_path.suffix != ".py" or file_path.stem == "__init__":
                return False
        # path.is_dir is True
        elif not deeply or file_path.name == "__pycache__":
            return False
        return True


_instance: _TaskManager | None = None


def get_instance() -> _TaskManager:
    global _instance
    if _instance is None:
        _instance = _TaskManager()
    return _instance
