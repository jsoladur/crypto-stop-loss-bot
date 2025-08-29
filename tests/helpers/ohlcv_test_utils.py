import json
import logging
from os import listdir, path
from typing import Any

from faker import Faker

from tests.helpers.constants import BUY_SELL_SIGNALS_MOCK_FILES_PATH

logger = logging.getLogger(__name__)


def get_fetch_ohlcv_random_result(faker: Faker) -> list[list[Any]]:
    fetch_ohlcv_return_value_filename = faker.random_element(
        [filename for filename in listdir(BUY_SELL_SIGNALS_MOCK_FILES_PATH) if filename.endswith(".json")]
    )
    ret = load_ohlcv_result_by_filename(fetch_ohlcv_return_value_filename)
    logger.info(
        f"[RANDOM OHLCV] Mock file {fetch_ohlcv_return_value_filename} loaded..."
        + f" Number of candlesticks: {len(ret)} "
    )
    return ret


def load_ohlcv_result_by_filename(fetch_ohlcv_return_value_filename: str) -> list[list[Any]]:
    with open(path.join(BUY_SELL_SIGNALS_MOCK_FILES_PATH, fetch_ohlcv_return_value_filename)) as fd:
        filecontent = fd.read()
        fetch_ohlcv_return_value = json.loads(filecontent)
    return fetch_ohlcv_return_value
