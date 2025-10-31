import logging
from datetime import UTC, datetime
from io import BytesIO

import pandas as pd

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from crypto_trailing_stop.infrastructure.services.vo.global_summary import GlobalSummary

logger = logging.getLogger(__name__)


class GlobalSummaryService:
    def __init__(self, operating_exchange_service: AbstractOperatingExchangeService) -> None:
        self._operating_exchange_service = operating_exchange_service

    async def get_global_summary(self) -> GlobalSummary:
        """
        Retrieves the global summary of the Exchange account.
        This method currently processes local Excel files to calculate total deposits,
        withdrawals, and current value.
        """
        if (
            operating_exchange := self._operating_exchange_service.get_operating_exchange()
        ) != OperatingExchangeEnum.BIT2ME:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
        total_deposits = 0.0
        withdrawls = 0.0
        async with await self._operating_exchange_service.get_client() as client:
            account_info = await self._operating_exchange_service.get_account_info(client=client)
            operation_types = set()
            for current_year in range(account_info.registration_date.year, datetime.now(UTC).year + 1):
                current_excel_file_content = await self._operating_exchange_service.get_accounting_summary_by_year(
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

            portfolio_balance = await self._operating_exchange_service.retrieve_porfolio_balance(
                user_currency=account_info.currency_code, client=client
            )
            global_summary = GlobalSummary(
                total_deposits=total_deposits, withdrawls=withdrawls, current_value=portfolio_balance.total_balance
            )
            return global_summary
