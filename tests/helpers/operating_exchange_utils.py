from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.constants import MOCK_SYMBOLS_EUR, MOCK_SYMBOLS_USDT


def get_random_symbol_by_operating_exchange(faker: Faker, operating_exchange: OperatingExchangeEnum) -> str:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            symbol = faker.random_element(MOCK_SYMBOLS_EUR)
        case OperatingExchangeEnum.MEXC:
            symbol = faker.random_element(MOCK_SYMBOLS_USDT)
        case _:
            raise ValueError(f"Unknown operating exchange: {operating_exchange}")
    return symbol
