import logging
import sys
from os import path, listdir
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crypto_trailing_stop.config import get_configuration_properties, get_dispacher
from crypto_trailing_stop.infrastructure.tasks import TaskManager
from crypto_trailing_stop.interfaces.controllers.health_controller import (
    router as health_router,
)
from crypto_trailing_stop.interfaces.controllers.login_controller import (
    router as login_router,
)

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import importlib

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


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
    bot = Bot(
        token=configuration_properties.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # And the run events dispatching
    dp = get_dispacher()
    await dp.start_polling(bot)
    yield


def main() -> FastAPI:
    global app
    if app is None:
        # Create FastAPI app with lifespan context manager
        # to initialize TaskManager
        # and clean up resources on shutdown
        # (if needed)
        app = FastAPI(lifespan=lifespan)
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
    return app


app = main()
