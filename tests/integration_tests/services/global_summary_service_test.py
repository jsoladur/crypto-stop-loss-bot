import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto, Profile
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_porfolio_balance_dto import (
    Bit2MePortfolioBalanceDto,
    ConvertedBalanceDto,
    TotalDto,
)
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeSummaryXlsxObjectMother

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_calculate_global_summary_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env
    global_summary_service: GlobalSummaryService = (
        get_application_container().infrastructure_container().services_container().global_summary_service()
    )
    _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    global_summary = await global_summary_service.get_global_summary()

    logger.info(repr(global_summary))

    assert global_summary is not None

    httpserver.check_assertions()


def _prepare_httpserver_mock(faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str) -> None:
    registration_year = datetime.now(UTC).year - 1

    # Get account registration date
    httpserver.expect(
        Bit2MeAPIRequestMacher("/bit2me-api/v1/account", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        Bit2MeAccountInfoDto(
            registrationDate=faker.date_time_between_dates(
                datetime_start=datetime(registration_year, 1, 1),
                datetime_end=datetime(registration_year, 12, 31, 23, 59, 59),
            ),
            profile=Profile(currency_code="EUR"),
        ).model_dump(mode="json", by_alias=True)
    )
    # Get summary of each year in order to calculate currency metrics
    for current_year in range(registration_year, datetime.now(UTC).year + 1):
        excel_filecontent = Bit2MeSummaryXlsxObjectMother.create(year=current_year)
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                f"/bit2me-api/v1/accounting/summary/{current_year}",
                method="GET",
                query_string=urlencode(
                    {"timeZone": "Europe/Madrid", "langCode": "en", "documentType": "xlsx"}, doseq=False
                ),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_data(excel_filecontent)

    # Portfolio balance
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/portfolio/balance",
            query_string=urlencode({"userCurrency": "EUR"}, doseq=False),
            method="GET",
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MePortfolioBalanceDto]](
            [
                Bit2MePortfolioBalanceDto(
                    serviceName="all",
                    total=TotalDto(
                        converted_balance=ConvertedBalanceDto(
                            currency="EUR", value=faker.pyfloat(min_value=1_000, max_value=3_000)
                        )
                    ),
                    wallets=[],
                )
            ]
        ).model_dump(mode="json", by_alias=True)
    )
