import logging
from pathlib import Path

from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from types import ModuleType

from crypto_trailing_stop.config import get_scheduler
from os import path, listdir
from importlib import import_module


logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self):
        self._scheduler = get_scheduler()
        self._scheduler.start()
        self._load_tasks()

    def _load_tasks(self, *, deeply: bool = True) -> None:
        self._tasks = {}
        modules = self._import_modules_by_dir(
            dir_to_imported=path.dirname(__file__),
            package=__package__,
            deeply=deeply,
        )
        for module in modules:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, AbstractTaskService)
                    and attr != AbstractTaskService
                ):
                    logger.info(f"Loading {attr.__name__}...")
                    self._tasks[id(attr)] = attr()
                    logger.info(f"{attr.__name__} has been loaded successfully...")

    def get_tasks(self) -> list[AbstractTaskService]:
        return list(self._tasks.values())

    def _import_modules_by_dir(
        self, dir_to_imported: str, package: str, *, deeply: bool = False
    ) -> list[ModuleType]:
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
                map(
                    lambda f: Path(path.realpath(path.join(dir_to_imported, f))),
                    listdir(dir_to_imported),
                ),
            )
        )
        for file_path in filter_files_in_dir:
            if file_path.is_dir():
                imported_modules.extend(
                    self._import_modules_by_dir(
                        dir_to_imported=path.realpath(file_path),
                        package=f"{package}.{file_path.stem}",
                        deeply=deeply,
                    )
                )
            else:
                logger.info(f"Importing modules from {file_path.name}...")
                imported_modules.append(
                    import_module(f".{file_path.stem}", package=package)
                )
                logger.debug(
                    "Modules has been imported "
                    f"from {file_path.name} has been loaded successfully..."
                )
        return imported_modules

    def _is_scan_candidate_file_to_import(
        self, file_path: Path, deeply: bool = False
    ) -> bool:
        if file_path.is_file():
            if file_path.suffix != ".py" or file_path.stem == "__init__":
                return False
        # path.is_dir == True
        elif not deeply or file_path.name == "__pycache__":
            return False
        return True
