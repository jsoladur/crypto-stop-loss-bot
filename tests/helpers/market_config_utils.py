import json
from os import path
from typing import Any

from pydantic import RootModel

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_exchange_info_dto import (
    MEXCExchangeInfoDto,
    MEXCExchangeSymbolConfigDto,
)


def load_raw_mexc_exchange_info() -> dict[str, Any]:
    market_config_file_path = path.realpath(
        path.join(path.dirname(__file__), "resources", "mexc", "exchange_info.json")
    )
    with open(market_config_file_path) as fd:
        exchange_info_content = fd.read()
    ret = json.loads(exchange_info_content)
    return ret


def load_mexc_exchange_info() -> MEXCExchangeInfoDto:
    exchange_info_content = load_raw_bit2me_market_config_list()
    exchange_info = MEXCExchangeInfoDto.model_validate(exchange_info_content)
    return exchange_info


def get_mexc_exchange_info_by_symbol(symbol: str) -> MEXCExchangeSymbolConfigDto:
    exchange_info = load_mexc_exchange_info()
    ret = next(filter(lambda market_config: market_config.symbol == symbol, exchange_info.symbols))
    return ret


def load_raw_bit2me_market_config_list() -> list[dict[str, Any]]:
    market_config_file_path = path.realpath(
        path.join(path.dirname(__file__), "resources", "bit2me", "market_config.json")
    )
    with open(market_config_file_path) as fd:
        market_config_content = fd.read()
    ret = json.loads(market_config_content)
    return ret


def load_bit2me_market_config_list() -> list[Bit2MeMarketConfigDto]:
    market_config_content = load_raw_bit2me_market_config_list()
    market_config_list = RootModel[list[Bit2MeMarketConfigDto]].model_validate(market_config_content).root
    return market_config_list


def get_bit2me_market_config_by_symbol(symbol: str) -> Bit2MeMarketConfigDto:
    market_config_list = load_bit2me_market_config_list()
    ret = next(filter(lambda market_config: market_config.symbol == symbol, market_config_list))
    return ret
