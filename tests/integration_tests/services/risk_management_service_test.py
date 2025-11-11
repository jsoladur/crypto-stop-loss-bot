import logging

import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.commons.constants import STOP_LOSS_STEPS_VALUE_LIST
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.risk_management_service import RiskManagementService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_get_and_set_risk_management_percent_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _ = integration_test_jobs_disabled_env
    risk_management_service: RiskManagementService = (
        get_application_container().infrastructure_container().services_container().risk_management_service()
    )

    first_value = await risk_management_service.get_risk_value()
    assert first_value == STOP_LOSS_STEPS_VALUE_LIST[-1]

    expected_value = round(faker.pyfloat(min_value=1, max_value=5), ndigits=2)
    await risk_management_service.set_risk_value(expected_value)

    returned_value = await risk_management_service.get_risk_value()
    assert expected_value == returned_value
