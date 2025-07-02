import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from faker import Faker

from crypto_trailing_stop.infrastructure.services.enums import SessionKeysEnum
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_get_or_create_fsm_context(faker: Faker) -> None:
    session_storage_service = SessionStorageService()
    fsm_context = await session_storage_service.get_or_create_fsm_context(
        bot_id=faker.random_number(digits=9, fix_len=True),
        chat_id=faker.random_number(digits=9, fix_len=True),
        user_id=faker.random_number(digits=9, fix_len=True),
    )
    assert fsm_context is not None


@pytest.mark.asyncio
async def should_return_true_when_user_is_logged(faker: Faker) -> None:
    data = {SessionKeysEnum.USER_CONTEXT.value: faker.simple_profile()}
    session_storage_service = SessionStorageService()
    # Create a mock FSMContext instance
    mock_fsm_context = MagicMock(spec=FSMContext)
    mock_fsm_context.get_data = AsyncMock(return_value=data)
    # Call the method
    result = await session_storage_service.is_user_logged(mock_fsm_context)
    # Assert the result
    assert result is True


@pytest.mark.asyncio
async def should_set_user_logged(faker: Faker) -> None:
    data = {}
    session_storage_service = SessionStorageService()

    mock_fsm_context = MagicMock(spec=FSMContext)
    mock_fsm_context.get_data = AsyncMock(return_value=data)
    mock_fsm_context.update_data = AsyncMock()

    result = await session_storage_service.is_user_logged(mock_fsm_context)
    assert result is False

    await session_storage_service.set_user_logged(mock_fsm_context, userinfo=faker.simple_profile())

    # Mock `get_data` to simulate user is now logged in
    mock_fsm_context.get_data = AsyncMock(return_value={SessionKeysEnum.USER_CONTEXT.value: faker.simple_profile()})

    result = await session_storage_service.is_user_logged(mock_fsm_context)
    assert result is True


@pytest.mark.asyncio
async def should_perform_logout(faker: Faker) -> None:
    user_data = {SessionKeysEnum.USER_CONTEXT.value: faker.simple_profile()}
    session_storage_service = SessionStorageService()

    mock_fsm_context = MagicMock(spec=FSMContext)
    mock_fsm_context.get_data = AsyncMock(return_value=user_data)
    mock_fsm_context.update_data = AsyncMock()

    result = await session_storage_service.is_user_logged(mock_fsm_context)
    assert result is True

    await session_storage_service.perform_logout(mock_fsm_context)

    # Simulate `get_data` after logout (no USER_CONTEXT)
    mock_fsm_context.get_data = AsyncMock(return_value={})

    result = await session_storage_service.is_user_logged(mock_fsm_context)
    assert result is False
