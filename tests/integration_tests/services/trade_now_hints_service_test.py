import logging
from unittest.mock import patch

import ccxt.async_support as ccxt
import pytest
from faker import Faker
from pytest_httpserver import HTTPServer

from crypto_trailing_stop.commons.constants import LEVERAGE_VALUES_LIST
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.favourite_crypto_currencies_test_utils import prepare_favourite_crypto_currencies
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_account_info_mock,
    prepare_httpserver_fetch_ohlcv_mock,
    prepare_httpserver_retrieve_portfolio_balance_mock,
    prepare_httpserver_tickers_list_mock,
)
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, MEXCTickerPriceAndBookDtoObjectMother

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_calculate_trade_now_hints_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_jobs_disabled_env
    trade_now_hints_service = (
        get_application_container().infrastructure_container().services_container().trade_now_hints_service()
    )
    favourite_crypto_currency, favourite_symbol, fetch_ohlcv_return_value = await _prepare_httpserver_mock(
        faker, httpserver, operating_exchange, api_key, api_secret
    )
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        result = await trade_now_hints_service.get_trade_now_hints(
            symbol=favourite_crypto_currency, leverage_value=faker.random_element(LEVERAGE_VALUES_LIST)
        )
    else:
        with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
            result = await trade_now_hints_service.get_trade_now_hints(
                symbol=favourite_crypto_currency, leverage_value=faker.random_element(LEVERAGE_VALUES_LIST)
            )

    httpserver.check_assertions()

    assert result is not None
    assert result.symbol == favourite_symbol
    assert result.leverage_value is not None
    assert result.tickers is not None
    assert result.crypto_market_metrics is not None
    assert result.fiat_wallet_percent_assigned is not None
    assert result.stop_loss_percent_value is not None
    assert result.take_profit_percent_value is not None
    assert result.profit_factor is not None

    # Assert Long position hints
    assert result.long is not None
    assert result.long.position_type == "Long"
    assert result.long.entry_price is not None
    assert result.long.stop_loss_price is not None
    assert result.long.take_profit_price is not None
    assert result.long.required_margin_eur is not None
    assert result.long.position_size_eur is not None
    assert result.long.loss_at_stop_loss_eur is not None
    assert result.long.risk_as_percent_of_total_capital is not None
    assert result.long.liquidation_price is not None
    assert result.long.is_safe_from_liquidation is not None

    # Assert Short position hints
    assert result.short is not None
    assert result.short.position_type == "Short"
    assert result.short.entry_price is not None
    assert result.short.stop_loss_price is not None
    assert result.short.take_profit_price is not None
    assert result.short.required_margin_eur is not None
    assert result.short.position_size_eur is not None
    assert result.short.loss_at_stop_loss_eur is not None
    assert result.short.risk_as_percent_of_total_capital is not None
    assert result.short.liquidation_price is not None
    assert result.short.is_safe_from_liquidation is not None


async def _prepare_httpserver_mock(
    faker: Faker, httpserver: HTTPServer, operating_exchange: OperatingExchangeEnum, api_key: str, api_secret: str
) -> tuple[str, str, list[tuple[float, float]]]:
    favourite_crypto_currencies = await prepare_favourite_crypto_currencies(faker)
    favourite_crypto_currency = faker.random_element(favourite_crypto_currencies)
    account_info = prepare_httpserver_account_info_mock(faker, httpserver, operating_exchange, api_key, api_secret)
    favourite_symbol = f"{favourite_crypto_currency}/{account_info.currency_code}"
    prepare_httpserver_retrieve_portfolio_balance_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        user_currency=account_info.currency_code.upper(),
        wallet_balances_crypto_currencies=favourite_crypto_currencies,
    )
    fetch_ohlcv_return_value = prepare_httpserver_fetch_ohlcv_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, favourite_symbol
    )
    symbols = [f"{crypto_currency}/{account_info.currency_code}" for crypto_currency in favourite_crypto_currencies]
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        tickers_list = Bit2MeTickersDtoObjectMother.list(symbols=symbols)
        unique_tickers = [tickers for tickers in tickers_list if tickers.symbol == favourite_symbol]
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        tickers_list = MEXCTickerPriceAndBookDtoObjectMother.list(symbols=symbols)
        unique_tickers = [
            (ticker_price, ticker_book)
            for ticker_price, ticker_book in tickers_list
            if ticker_price.symbol == "".join(favourite_symbol.split("/"))
        ]
    else:
        raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    if not unique_tickers:
        raise ValueError("No unique tickers found")
    prepare_httpserver_tickers_list_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret=api_secret,
        unique_tickers=unique_tickers,
        tickers_list=tickers_list,
    )
    return favourite_crypto_currency, favourite_symbol, fetch_ohlcv_return_value
