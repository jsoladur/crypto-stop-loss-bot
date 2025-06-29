from importlib import import_module
from inspect import isclass
from os import listdir, makedirs, path

from piccolo.engine.sqlite import SQLiteEngine
from piccolo.table import Table

from crypto_trailing_stop.config import get_configuration_properties


async def init_database() -> None:
    configuration_properties = get_configuration_properties()
    if configuration_properties.database_in_memory:
        engine = SQLiteEngine(path=":memory:")
    else:
        makedirs(path.dirname(configuration_properties.database_path), exist_ok=True)
        engine = SQLiteEngine(path=configuration_properties.database_path)
    # Set up the database
    for model_filename in listdir(path.relpath(path.join(path.dirname(__file__), "models"))):
        if model_filename.endswith(".py") and model_filename != "__init__.py":
            module_name = model_filename[:-3]
            module = import_module(f".models.{module_name}", package=__package__)
            for obj_name in dir(module):
                obj = getattr(module, obj_name)
                if isclass(obj) and issubclass(obj, Table) and obj is not Table:
                    obj._meta.db = engine
                    await obj.create_table(if_not_exists=True)
