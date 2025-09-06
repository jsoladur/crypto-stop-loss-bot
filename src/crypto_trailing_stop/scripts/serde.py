import logging
from dataclasses import asdict, fields

import pandas as pd

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult

logger = logging.getLogger(__name__)


class BacktestResultSerde:
    """
    Service to Serialize and Deserialize backtesting results
    to and from the Parquet format.
    """

    def save(self, results: list[BacktestingExecutionResult], filepath: str) -> None:
        # Convert to list of dicts
        dict_results = [asdict(result) for result in results]
        # Flatten with json_normalize
        df = pd.json_normalize(dict_results, sep=".")
        # Save to Parquet
        df.to_parquet(filepath, index=False)
        logger.info(f"✅ Successfully saved {len(results)} results to {filepath}")

    def load(self, filepath: str, *, drop_na: bool = True) -> list[BacktestingExecutionResult]:
        """
        Deserializes a Parquet file back into a list of BacktestingExecutionResult objects.

        :param filepath: The path of the Parquet file to load.
        :return: A list of BacktestingExecutionResult objects.
        """
        df = pd.read_parquet(filepath)
        if drop_na:
            df.dropna(inplace=True)
        results = []
        # Get field names for reconstruction
        config_fields = {f.name for f in fields(BuySellSignalsConfigItem)}
        result_fields = {f.name for f in fields(BacktestingExecutionResult)}

        for _, row in df.iterrows():
            row_dict = row.to_dict()

            # Extract nested parameters.* keys
            params_data = {
                key.split("parameters.")[1]: value
                for key, value in row_dict.items()
                if key.startswith("parameters.") and key.split("parameters.")[1] in config_fields
            }
            config_item = BuySellSignalsConfigItem(**params_data)
            # Extract top-level fields
            result_data = {key: row_dict[key] for key in result_fields if key in row_dict and key != "parameters"}
            # Rebuild dataclass
            result_item = BacktestingExecutionResult(parameters=config_item, **result_data)
            results.append(result_item)
        logger.info(f"✅ Successfully loaded {len(results)} results from {filepath}")
        return results
