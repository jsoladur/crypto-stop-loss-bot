from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, override

from crypto_trailing_stop.commons.constants import MEXC_TAKER_FEES
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_exchange_info_dto import MEXCExchangeSymbolConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.remote.mexc_remote_service import MEXCRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.base import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import (
    OperatingExchangeEnum,
    OrderSideEnum,
    OrderStatusEnum,
    OrderTypeEnum,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo import (
    AccountInfo,
    Order,
    PortfolioBalance,
    SymbolMarketConfig,
    SymbolTickers,
    Trade,
    TradingWalletBalance,
)

if TYPE_CHECKING:
    from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe


class MEXCOperatingExchangeService(AbstractOperatingExchangeService):
    def __init__(self, mexc_remote_service: MEXCRemoteService) -> None:
        super().__init__()
        self._mexc_remote_service = mexc_remote_service

    @override
    async def get_account_info(self, *, client: Any | None = None) -> AccountInfo:
        return AccountInfo(currency_code="USDT")

    @override
    async def get_trading_wallet_balances(
        self, symbols: list[str] | str | None = None, *, client: Any | None = None
    ) -> list[TradingWalletBalance]:
        account_info = await self._mexc_remote_service.get_account_info(client=client)
        return [
            TradingWalletBalance(
                currency=balance.asset.upper().strip(), balance=balance.free, blocked_balance=balance.locked
            )
            for balance in account_info.balances
            if symbols is None or balance.asset.upper().strip() in [s.upper().strip() for s in symbols]
        ]

    @override
    async def retrieve_porfolio_balance(self, user_currency: str, *, client: Any | None = None) -> PortfolioBalance:
        raise NotImplementedError("To be implemented")

    @override
    async def get_single_tickers_by_symbol(self, symbol: str, *, client: Any | None = None) -> SymbolTickers:
        mexc_symbol = self._to_mexc_symbol_repr(symbol)
        ticker_price = await self._mexc_remote_service.get_ticker_price(symbol=mexc_symbol, client=client)
        ticker_book = await self._mexc_remote_service.get_ticker_book(symbol=mexc_symbol, client=client)
        ret = self._map_symbol_tickers(symbol, ticker_price, ticker_book)
        return ret

    @override
    async def get_tickers_by_symbols(
        self, symbols: list[str] | str = [], *, client: Any | None = None
    ) -> list[SymbolTickers]:
        mexc_exchange_symbol_config_dict = await self._get_mexc_exchange_symbol_config(client=client)
        ticker_prices = await self._mexc_remote_service.get_ticker_price_list(client=client)
        ticker_books = await self._mexc_remote_service.get_ticker_book_list(client=client)
        ret = []
        for ticker_price in ticker_prices:
            symbol_config = mexc_exchange_symbol_config_dict.get(ticker_price.symbol, None)
            if symbol_config:
                symbol = f"{symbol_config.base_asset}/{symbol_config.quote_asset}"
                ticker_book = next((book for book in ticker_books if book.symbol == ticker_price.symbol), None)
                ret.append(self._map_symbol_tickers(symbol, ticker_price, ticker_book))
        symbols = list(symbols) if isinstance(symbols, (list, set, tuple, frozenset)) else [symbols]
        if symbols:
            ret = [tickers for tickers in ret if tickers.symbol in symbols]
        return ret

    @override
    async def get_orders(
        self,
        *,
        side: OrderSideEnum | None = None,
        order_type: OrderTypeEnum | None = None,
        status: list[OrderStatusEnum] | OrderStatusEnum | None = None,
        symbol: str | None = None,
        client: Any | None = None,
    ) -> list[Order]:
        raise NotImplementedError("To be implemented")

    @override
    async def get_order_by_id(self, id: str, *, client: Any | None = None) -> Order | None:
        raise NotImplementedError("To be implemented")

    @override
    async def get_trades(
        self, *, side: OrderSideEnum | None = None, symbol: str | None = None, client: Any | None = None
    ) -> list[Trade]:
        raise NotImplementedError("To be implemented")

    @override
    async def fetch_ohlcv(
        self, symbol: str, timeframe: "Timeframe", limit: int = 251, *, client: Any | None = None
    ) -> list[list[Any]]:
        raise NotImplementedError("To be implemented")

    @override
    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        mexc_exchange_symbol_config_dict = await self._get_mexc_exchange_symbol_config(client=client)
        spot_trading_usdt_symbols = [
            symbol_info
            for symbol_info in mexc_exchange_symbol_config_dict.values()
            if symbol_info.is_spot_trading_allowed and symbol_info.quote_asset == "USDT"
        ]
        ret: dict[str, SymbolMarketConfig] = {}
        for symbol_info in spot_trading_usdt_symbols:
            symbol = f"{symbol_info.base_asset}/{symbol_info.quote_asset}"
            ret[symbol] = SymbolMarketConfig(
                symbol=symbol,
                price_precision=symbol_info.quote_precision,
                amount_precision=abs(Decimal(symbol_info.base_size_precision).as_tuple().exponent),
            )
        return ret

    async def _get_mexc_exchange_symbol_config(
        self, *, client: Any | None = None
    ) -> dict[str, MEXCExchangeSymbolConfigDto]:
        exchange_info = await self._mexc_remote_service.get_exchange_info(client=client)
        return {symbol_info.symbol: symbol_info for symbol_info in exchange_info.symbols}

    @override
    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        raise NotImplementedError("To be implemented")

    @override
    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        raise NotImplementedError("To be implemented")

    @override
    async def get_accounting_summary_by_year(self, year: str, *, client: Any | None = None) -> bytes:
        raise NotImplementedError("This method is not supported in MEXC")

    @override
    async def get_client(self) -> Any:
        return await self._mexc_remote_service.get_http_client()

    @override
    def has_global_summary_report(self) -> bool:
        return False

    @override
    def get_taker_fee(self) -> float:
        return MEXC_TAKER_FEES

    @override
    def get_operating_exchange(self) -> OperatingExchangeEnum:
        return OperatingExchangeEnum.MEXC

    def _map_symbol_tickers(
        self, symbol: str, ticker_price: MEXCTickerPriceDto, ticker_book: MEXCTickerBookDto | None = None
    ) -> SymbolTickers:
        ret = SymbolTickers(
            timestamp=int(datetime.now(UTC).timestamp()),
            symbol=symbol,
            close=ticker_price.price,
            bid=ticker_book.bid_price if ticker_book else None,
            ask=ticker_book.ask_price if ticker_book else None,
        )
        return ret

    def _to_mexc_symbol_repr(self, symbol: str) -> str:
        ret = "".join(symbol.split("/"))
        return ret
