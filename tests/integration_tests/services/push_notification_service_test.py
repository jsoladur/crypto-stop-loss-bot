import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_save_or_update_push_notifications_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env
    push_notification_service = PushNotificationService()

    telegram_chat_id = faker.random_number(digits=9, fix_len=True)
    push_notification_items = await push_notification_service.find_push_notification_by_telegram_chat_id(
        telegram_chat_id
    )

    assert len(push_notification_items) == len(list(PushNotificationTypeEnum))
    assert all(global_flag_item.activated is False for global_flag_item in push_notification_items)

    notification_type = faker.random_element(list(PushNotificationTypeEnum))

    assert len(await push_notification_service.get_actived_subscription_by_type(notification_type)) <= 0

    push_notification_item = await push_notification_service.toggle_push_notification_by_type(
        telegram_chat_id, notification_type
    )

    assert push_notification_item.activated is True

    push_notification_item = await push_notification_service.toggle_push_notification_by_type(
        telegram_chat_id, notification_type
    )

    assert push_notification_item.activated is False

    push_notification_item = await push_notification_service.toggle_push_notification_by_type(
        telegram_chat_id, notification_type
    )
    actived_subscription_by_type = await push_notification_service.get_actived_subscription_by_type(notification_type)

    assert telegram_chat_id in actived_subscription_by_type

    push_notification_items = await push_notification_service.find_push_notification_by_telegram_chat_id(
        telegram_chat_id
    )

    assert any(
        push_notification_item.telegram_chat_id == telegram_chat_id and push_notification_item.activated is True
        for push_notification_item in push_notification_items
    )
