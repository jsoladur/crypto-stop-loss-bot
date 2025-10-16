import asyncio
import importlib
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from os import listdir, path

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.base import BaseScheduler
from dependency_injector.providers import Singleton
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.database import init_database
from crypto_trailing_stop.infrastructure.services.base import AbstractEventHandlerService
from crypto_trailing_stop.interfaces.controllers.health_controller import router as health_router
from crypto_trailing_stop.interfaces.controllers.login_controller import router as login_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

app: FastAPI | None = None


def _load_modules_by_folder(root_folder: str, root_package: str, folder_name: str) -> None:
    if path.exists(root_folder) and path.isdir(root_folder):
        current_folder = path.join(root_folder, folder_name)
        if path.exists(current_folder) and path.isdir(current_folder):
            for filename in listdir(current_folder):
                if path.isdir(path.join(current_folder, filename)):
                    _load_modules_by_folder(
                        root_folder=current_folder, root_package=f"{root_package}.{folder_name}", folder_name=filename
                    )
                elif filename.endswith(".py") and filename != "__init__.py":
                    module_name = f"{root_package}.{folder_name}.{filename[:-3]}"
                    importlib.import_module(module_name)


def _load_telegram_commands() -> None:
    for layer_name in ["commands", "callbacks"]:
        _load_modules_by_folder(
            root_folder=path.join(path.dirname(__file__), "interfaces", "telegram"),
            root_package=f"{__package__}.interfaces.telegram",
            folder_name=layer_name,
        )


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None]:
    application_container = get_application_container()
    configuration_properties: ConfigurationProperties = application_container.configuration_properties()
    dp: Dispatcher = application_container.dispatcher()
    scheduler: BaseScheduler = application_container.infrastructure_container().tasks_container().scheduler()

    # Initialize database
    await init_database()
    # Background task manager initialization
    task_manager = await application_container.infrastructure_container().tasks_container().task_manager().load_tasks()
    logger.info(f"{len(task_manager.get_tasks())} jobs have been loaded!")
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    # Telegram bot initialization
    # And the run events dispatching
    if configuration_properties.telegram_bot_enabled:  # pragma: no cover
        telegram_bot: Bot = application_container.interfaces_container().telegram_container().telegram_bot()
        asyncio.create_task(dp.start_polling(telegram_bot))
    if configuration_properties.background_tasks_enabled:
        scheduler.start()
    # Configure pyee listeners
    for provider in application_container.infrastructure_container().services_container().traverse(types=[Singleton]):
        dependency_object = provider()
        if isinstance(dependency_object, AbstractEventHandlerService):
            dependency_object.configure()
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
    application_container = get_application_container()
    configuration_properties: ConfigurationProperties = application_container.configuration_properties()
    version = application_container.application_version()
    app = FastAPI(
        title="Crypto Trailing Stop API",
        description="API for Crypto Trailing Stop Bot",
        version=version,
        contact={"name": "jmsoladev", "url": "https://www.jmsoladev.com", "email": "josemaria.sola.duran@gmail.com"},
        license_info={"name": "MIT License", "url": "https://opensource.org/license/mit/"},
        lifespan=_lifespan,
    )
    app.add_middleware(SessionMiddleware, secret_key=configuration_properties.session_secret_key)
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
