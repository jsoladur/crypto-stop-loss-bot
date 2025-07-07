import io
import random
import uuid
from datetime import UTC, datetime, timedelta

import pandas as pd
from faker import Faker

# Define constants for the Excel file generation
COLUMN_NAMES = [
    "Operation type",
    "To amount",
    "To currency",
    "From amount",
    "From currency",
    "Fee amount",
    "Fee currency",
    "Exchange",
    "Group",
    "Description",
    "Date",
]

OPERATION_TYPES = ["Deposit", "Staking", "Trade", "Withdrawal"]

# All currencies are EUR as per request
DEFAULT_CURRENCY = "EUR"

# Exchange is always Bit2Me as per request
DEFAULT_EXCHANGE = "Bit2Me"

GROUPS = ["bank-transfer", "pocket", "card", "earn", "saving"]


class Bit2MeSummaryXlsxObjectMother:
    _faker: Faker = Faker()

    @classmethod
    def create(
        cls,
        num_rows: int = 50,  # Default num_rows changed to 50
        year: int = datetime.now(UTC).year,  # New argument for the year, defaults to current year
    ) -> bytes:
        """
        Generates a fake Excel file with financial transaction data
        following the Object Mother pattern.

        Args:
            num_rows: The number of rows (transactions) to generate.
            year: The year for which the data should be generated.

        Returns:
            bytes: The content of the generated Excel file as bytes.
        """
        data = []

        # Define the absolute start and end of the specified year
        year_start = datetime(year, 1, 1, 0, 0, 0)
        year_end = datetime(year, 12, 31, 23, 59, 59)

        # Generate start_date and end_date within the specified year using faker
        start_date = cls._faker.date_time_between_dates(datetime_start=year_start, datetime_end=year_end)
        end_date = cls._faker.date_time_between_dates(datetime_start=start_date, datetime_end=year_end)

        # Calculate the total seconds between the Faker-generated start_date and end_date
        time_difference_seconds = int((end_date - start_date).total_seconds())

        for _ in range(num_rows):
            op_type = random.choice(OPERATION_TYPES)
            # Using _faker to generate amounts for more realistic data
            # pydecimal is good for financial data to avoid floating point issues
            to_amount = round(
                float(
                    cls._faker.pydecimal(left_digits=4, right_digits=6, min_value=0.1, max_value=5000.0, positive=True)
                ),
                6,
            )
            from_amount = round(
                float(
                    cls._faker.pydecimal(left_digits=4, right_digits=6, min_value=0.1, max_value=5000.0, positive=True)
                ),
                6,
            )
            fee_amount = round(
                float(
                    cls._faker.pydecimal(left_digits=2, right_digits=6, min_value=0.1, max_value=10.0, positive=True)
                ),
                6,
            )

            group = random.choice(GROUPS)

            # Generate a random datetime within the specified start_date and end_date range
            # Ensure time_difference_seconds is not zero if start_date == end_date
            if time_difference_seconds > 0:
                random_seconds_offset = random.randint(0, time_difference_seconds)
                random_date = start_date + timedelta(seconds=random_seconds_offset)
            else:
                random_date = start_date  # If start_date and end_date are the same, just use start_date

            date_str = random_date.strftime("%Y-%m-%d %H:%M")

            # Generate a descriptive string based on operation type
            description = ""
            if op_type == "Trade":
                description = (
                    f"Traded {from_amount} {DEFAULT_CURRENCY} for {to_amount} {DEFAULT_CURRENCY} on {cls._faker.word()}"
                )
            elif op_type == "Deposit":
                # Using faker for a more varied description
                description = f"Deposit to {cls._faker.bank_country()} bank account via credit card"
            elif op_type == "Withdrawal":
                # Using faker for a more varied description
                description = f"Withdrawal to {cls._faker.bank_country()} bank account for wallet {uuid.uuid4()}"
            elif op_type == "Staking":
                description = f"Staking rewards in {group} program from {cls._faker.company()}"
            else:
                description = cls._faker.sentence(nb_words=8)  # Generic sentence if needed

            row = {
                "Operation type": op_type,
                "To amount": to_amount,
                "To currency": DEFAULT_CURRENCY,
                "From amount": from_amount if op_type == "Trade" else "",
                "From currency": DEFAULT_CURRENCY if op_type == "Trade" else "",
                "Fee amount": fee_amount,
                "Fee currency": DEFAULT_CURRENCY,
                "Exchange": DEFAULT_EXCHANGE,
                "Group": group,
                "Description": description,
                "Date": date_str,
            }
            data.append(row)

        # Create the main DataFrame from the generated data
        actual_data_df = pd.DataFrame(data)

        # Create an empty row DataFrame
        # Initialize with empty strings for all columns to ensure consistency in Excel
        empty_row_data = {col: "" for col in COLUMN_NAMES}
        empty_df = pd.DataFrame([empty_row_data], columns=COLUMN_NAMES)

        # Create a DataFrame for the column names themselves, to be placed as a row
        header_as_data_df = pd.DataFrame([COLUMN_NAMES], columns=COLUMN_NAMES)

        # Concatenate the empty row, then the header row (as data), then the actual data
        df_final = pd.concat([empty_df, header_as_data_df, actual_data_df], ignore_index=True)

        # Save DataFrame to an in-memory bytes buffer
        # Set header=False because the header is now part of the DataFrame's content
        output = io.BytesIO()
        df_final.to_excel(output, index=False, header=False)
        output.seek(0)  # Rewind to the beginning of the stream
        return output.getvalue()
