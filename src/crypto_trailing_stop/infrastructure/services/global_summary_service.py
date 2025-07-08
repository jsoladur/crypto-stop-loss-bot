import logging
from datetime import UTC, datetime
from io import BytesIO

import pandas as pd
import pydash
from httpx import Client

from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.vo.global_summary import GlobalSummary

logger = logging.getLogger(__name__)


class GlobalSummaryService:
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._bit2me_remote_service = bit2me_remote_service

    async def get_global_summary(self) -> GlobalSummary:
        """
        Retrieves the global summary of Bit2Me transactions.
        This method currently processes local Excel files to calculate total deposits,
        withdrawals, and current value.
        """
        total_deposits = 0.0
        withdrawls = 0.0
        async with await self._bit2me_remote_service.get_http_client() as client:
            account_info = await self._bit2me_remote_service.get_account_info(client=client)
            operation_types = set()
            for current_year in range(account_info.registration_date.year, datetime.now(UTC).year + 1):
                current_excel_file_content = await self._bit2me_remote_service.get_accounting_summary_by_year(
                    year=str(current_year), client=client
                )
                df = pd.read_excel(BytesIO(current_excel_file_content), header=1, sheet_name=None)
                for _, sheet_data in df.items():
                    operation_types.update(sheet_data["Operation type"].unique().tolist())
                    filtered_df = sheet_data[sheet_data["Operation type"] == "Deposit"]
                    total_deposits += filtered_df["From amount"].sum()

                    filtered_df = sheet_data[sheet_data["Operation type"] == "Withdrawal"]
                    withdrawls += filtered_df["From amount"].sum()

            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"Operation type found out are: {','.join(operation_types)}")

            current_value = await self.calculate_portfolio_total_fiat_amount(
                account_info.profile.currency_code, client=client
            )
            global_summary = GlobalSummary(
                total_deposits=total_deposits, withdrawls=withdrawls, current_value=current_value
            )
            return global_summary

    async def calculate_portfolio_total_fiat_amount(self, currency_code: str, *, client: Client | None = None) -> float:
        balances = await self._bit2me_remote_service.retrieve_porfolio_balance(
            user_currency=currency_code.lower(), client=client
        )
        balances_by_service_name = pydash.group_by(balances, lambda b: b.service_name)
        current_value = round(
            pydash.sum_(
                [
                    current_balance.total.converted_balance.value
                    for current_balance in balances_by_service_name.get("all", [])
                ]
            ),
            ndigits=2,
        )
        return current_value
