import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.risk_management_service import RiskManagementService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
risk_management_service: RiskManagementService = (
    application_container.infrastructure_container().services_container().risk_management_service()
)


@dp.callback_query(lambda c: c.data == "risk_management_home")
async def risk_management_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            risk_percent_value = await risk_management_service.get_risk_value()
            await callback_query.message.answer(
                "ℹ️ Click on the current risk value in order to change it",
                reply_markup=keyboards_builder.get_risk_management_home_keyboard(risk_percent_value),
            )
        except Exception as e:
            logger.error(f"Error retrieving risk percent value: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving risk percent value. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the risk percent value (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
