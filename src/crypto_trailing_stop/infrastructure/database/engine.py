from importlib import import_module
from inspect import isclass
from os import listdir, makedirs, path

from piccolo.engine.base import Engine
from piccolo.engine.sqlite import SQLiteEngine
from piccolo.table import Table

_engine: Engine | None = None


async def init_database() -> None:
    global _engine

    # FIXME: Review this import here!
    from crypto_trailing_stop.config.dependencies import get_application_container

    application_container = get_application_container()
    configuration_properties = application_container.configuration_properties()
    if configuration_properties.database_in_memory:  # pragma: no cover
        _engine = SQLiteEngine(path=":memory:")
    else:
        makedirs(path.dirname(configuration_properties.database_path), exist_ok=True)
        _engine = SQLiteEngine(path=configuration_properties.database_path)
    # Set up the database
    for model_filename in listdir(path.relpath(path.join(path.dirname(__file__), "models"))):
        if model_filename.endswith(".py") and model_filename != "__init__.py":
            module_name = model_filename[:-3]
            module = import_module(f".models.{module_name}", package=__package__)
            for obj_name in dir(module):
                obj = getattr(module, obj_name)
                if isclass(obj) and issubclass(obj, Table) and obj is not Table:
                    obj._meta.db = _engine
                    await obj.create_table(if_not_exists=True)


def get_engine() -> Engine:
    if _engine is None:
        raise ValueError("Database not initialized")
    return _engine
