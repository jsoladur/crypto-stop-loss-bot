import json
from os import path
from typing import Any

from pydantic import RootModel

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto


def load_raw_market_config_list() -> list[dict[str, Any]]:
    market_config_file_path = path.realpath(
        path.join(path.dirname(__file__), "resources", "bit2me", "market_config.json")
    )
    with open(market_config_file_path) as fd:
        market_config_content = fd.read()
    ret = json.loads(market_config_content)
    return ret


def load_market_config_list() -> list[Bit2MeMarketConfigDto]:
    market_config_content = load_raw_market_config_list()
    market_config_list = RootModel[list[Bit2MeMarketConfigDto]].model_validate(market_config_content).root
    return market_config_list


def get_market_config_by_symbol(symbol: str) -> Bit2MeMarketConfigDto:
    market_config_list = load_market_config_list()
    ret = next(filter(lambda market_config: market_config.symbol == symbol, market_config_list))
    return ret
