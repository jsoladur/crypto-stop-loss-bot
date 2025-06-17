import logging
import sys
import asyncio
from os import path, listdir
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crypto_trailing_stop.config import (
    get_configuration_properties,
    get_dispacher,
    get_telegram_bot,
    get_scheduler,
)
from crypto_trailing_stop.infrastructure.tasks import TaskManager
from crypto_trailing_stop.interfaces.controllers.health_controller import (
    router as health_router,
)
from crypto_trailing_stop.interfaces.controllers.login_controller import (
    router as login_router,
)
import importlib

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

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
                module_name = (
                    f"{__package__}.interfaces.telegram.{layer_name}.{filename[:-3]}"
                )
                try:
                    importlib.import_module(module_name)
                except ModuleNotFoundError:
                    logging.warning(
                        f"Module {module_name} not found. Skipping dynamic import."
                    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Background task manager initialization
    TaskManager()
    # Telegram bot initialization
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    configuration_properties = get_configuration_properties()

    # And the run events dispatching
    dp = get_dispacher()
    if configuration_properties.telegram_bot_enabled:
        asyncio.create_task(dp.start_polling(get_telegram_bot()))

    scheduler = get_scheduler()
    if configuration_properties.background_tasks_enabled:
        scheduler.start()

    logger.info("Application startup complete.")
    # Yield control back to the FastAPI apps
    yield

    # Cleanup on shutdown
    if configuration_properties.telegram_bot_enabled:
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
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware, secret_key=configuration_properties.session_secret_key
    )
    configuration_properties = get_configuration_properties()
    if configuration_properties.cors_enabled:
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
