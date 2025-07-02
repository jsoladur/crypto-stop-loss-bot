import asyncio
import importlib
import logging
import sys
import tomllib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from os import getcwd, listdir, path
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from crypto_trailing_stop.config import get_configuration_properties, get_dispacher, get_scheduler, get_telegram_bot
from crypto_trailing_stop.infrastructure.database import init_database
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.interfaces.controllers.health_controller import router as health_router
from crypto_trailing_stop.interfaces.controllers.login_controller import router as login_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

app: FastAPI | None = None


def _load_telegram_commands() -> None:
    for layer_name in ["commands", "callbacks"]:
        _load_telegram_layer(layer_name)


def _load_telegram_layer(layer_name: str) -> None:
    folder = path.join(path.dirname(__file__), "interfaces", "telegram", layer_name)
    if path.exists(folder) and path.isdir(folder):
        for filename in listdir(folder):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"{__package__}.interfaces.telegram.{layer_name}.{filename[:-3]}"
                try:
                    importlib.import_module(module_name)
                except ModuleNotFoundError:  # pragma: no cover
                    logging.warning(f"Module {module_name} not found. Skipping dynamic import.")


def _get_project_version() -> str:
    pyproject_path = Path(getcwd()) / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    ret = pyproject["project"]["version"]
    return ret


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Initialize database
    await init_database()
    # Background task manager initialization
    task_manager = await get_task_manager_instance().load_tasks()
    logger.info(f"{len(task_manager.get_tasks())} jobs have been loaded!")
    # Telegram bot initialization
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    configuration_properties = get_configuration_properties()

    # And the run events dispatching
    dp = get_dispacher()
    if configuration_properties.telegram_bot_enabled:  # pragma: no cover
        asyncio.create_task(dp.start_polling(get_telegram_bot()))

    scheduler = get_scheduler()
    if configuration_properties.background_tasks_enabled:
        scheduler.start()

    logger.info("Application startup complete.")

    # Yield control back to the FastAPI apps
    yield

    # Cleanup on shutdown
    if configuration_properties.telegram_bot_enabled:  # pragma: no cover
        asyncio.create_task(dp.stop_polling())
    if configuration_properties.background_tasks_enabled:
        scheduler.shutdown()

    logger.info("Application shutdown complete.")


def _boostrap_app() -> None:
    global app
    # Create FastAPI app with lifespan context manager
    configuration_properties = get_configuration_properties()
    # to initialize TaskManager
    # and clean up resources on shutdown
    # (if needed)
    version = _get_project_version()
    app = FastAPI(
        title="Crypto Trailing Stop API",
        description="API for Crypto Trailing Stop Bot",
        version=version,
        contact={"name": "jmsoladev", "url": "https://www.jmsoladev.com", "email": "josemaria.sola.duran@gmail.com"},
        license_info={"name": "MIT License", "url": "https://opensource.org/license/mit/"},
        lifespan=_lifespan,
    )
    app.add_middleware(SessionMiddleware, secret_key=configuration_properties.session_secret_key)
    configuration_properties = get_configuration_properties()
    if configuration_properties.cors_enabled:  # pragma: no cover
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(login_router)
    # Include other routers here
    # e.g., app.include_router(other_router)

    # Load Telegram commands dynamically
    _load_telegram_commands()


def main() -> FastAPI:
    if app is None:
        _boostrap_app()
    return app


# Initialize the FastAPI app
app = main()
