import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_save_or_update_global_flag_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env
    application_container = get_application_container()
    global_flag_service: GlobalFlagService = (
        application_container.infrastructure_container().services_container().global_flag_service()
    )

    global_flag_items = await global_flag_service.find_all()
    assert len(global_flag_items) == len(list(GlobalFlagTypeEnum))
    assert all(global_flag_item.value is True for global_flag_item in global_flag_items)

    global_flag_type = faker.random_element(list(GlobalFlagTypeEnum))

    assert (await global_flag_service.is_enabled_for(global_flag_type)) is True

    await global_flag_service.force_disable_by_name(global_flag_type)

    assert (await global_flag_service.is_enabled_for(global_flag_type)) is False

    await global_flag_service.toggle_by_name(global_flag_type)

    assert (await global_flag_service.is_enabled_for(global_flag_type)) is True

    await global_flag_service.force_disable_by_name(global_flag_type)

    assert (await global_flag_service.is_enabled_for(global_flag_type)) is False

    await global_flag_service.force_disable_by_name(global_flag_type)

    assert (await global_flag_service.is_enabled_for(global_flag_type)) is False
