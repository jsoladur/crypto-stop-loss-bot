from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, override

import ccxt.async_support as ccxt
import pydash

from crypto_trailing_stop.commons.constants import MEXC_TAKER_FEES
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_exchange_info_dto import MEXCExchangeSymbolConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import (
    CreateNewMEXCOrderDto,
    MEXCOrderDto,
    MEXCOrderStatus,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_trade_dto import MEXCTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
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
    def __init__(self, mexc_remote_service: MEXCRemoteService, ccxt_remote_service: CcxtRemoteService) -> None:
        super().__init__()
        self._mexc_remote_service = mexc_remote_service
        self._ccxt_remote_service = ccxt_remote_service
        self._exchange = ccxt.mexc()

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
        trading_wallet_balances = await self.get_trading_wallet_balances(client=client)
        symbol_tickers_dict = {
            symbol_tickers.symbol: symbol_tickers.close
            for symbol_tickers in await self.get_tickers_by_symbols(client=client)
        }
        total_balance = sum(
            [
                (
                    trading_wallet_balance.total_balance
                    * symbol_tickers_dict[f"{trading_wallet_balance.currency}/{user_currency}"]
                )
                if trading_wallet_balance.currency.lower() != user_currency.lower()
                else trading_wallet_balance.total_balance
                for trading_wallet_balance in trading_wallet_balances
                if trading_wallet_balance.is_effective
            ]
        )
        ret = PortfolioBalance(total_balance=total_balance)
        return ret

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
        mexc_exchange_symbol_config_dict = await self._get_all_mexc_exchange_symbol_config(client=client)
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
        status = status or []
        status = status if isinstance(status, (list, set, tuple, frozenset)) else [status]
        mexc_symbol = self._to_mexc_symbol_repr(symbol) if symbol else None
        mexc_exchange_symbol_config_dict = await self._get_all_mexc_exchange_symbol_config(client=client)
        if OrderStatusEnum.OPEN in status or OrderStatusEnum.INACTIVE in status:
            mexc_orders = await self._mexc_remote_service.get_open_orders(symbol=mexc_symbol, client=client)
        else:
            mexc_orders = await self._mexc_remote_service.get_all_orders(symbol=mexc_symbol, client=client)
        ret: Order = [
            self._map_mexc_order(mexc_order, mexc_exchange_symbol_config_dict[mexc_order.symbol])
            for mexc_order in mexc_orders
        ]
        ret = [
            order
            for order in ret
            if (not status or order.status in status)
            and (not side or order.side == side)
            and (not order_type or order.order_type == order_type)
        ]
        return ret

    @override
    async def get_order_by_id(self, id: str, *, client: Any | None = None) -> Order | None:
        mexc_order = await self._mexc_remote_service.get_order_by_id(order_id=id, client=client)
        symbol_config = await self._get_single_mexc_exchange_symbol_config(symbol=mexc_order.symbol, client=client)
        ret = self._map_mexc_order(mexc_order, symbol_config)
        return ret

    @override
    async def get_trades(
        self, *, side: OrderSideEnum | None = None, symbol: str | None = None, client: Any | None = None
    ) -> list[Trade]:
        mexc_exchange_symbol_config_dict = await self._get_all_mexc_exchange_symbol_config(client=client)
        mexc_trades = await self._mexc_remote_service.get_trades(symbol=symbol, client=client)
        ret = [
            self._map_mexc_trade(mecx_trade, mexc_exchange_symbol_config_dict[mecx_trade.symbol])
            for mecx_trade in mexc_trades
        ]
        ret = [trade for trade in ret if (not side or trade.side == side)]
        return ret

    @override
    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        mexc_exchange_symbol_config_dict = await self._get_all_mexc_exchange_symbol_config(client=client)
        spot_trading_usdt_symbols = [
            symbol_info
            for symbol_info in mexc_exchange_symbol_config_dict.values()
            if "spot" in [permission.lower() for permission in symbol_info.permissions]
            and symbol_info.quote_asset == "USDT"
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

    @override
    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        create_order_obj = CreateNewMEXCOrderDto(
            side=order.side.value.upper(),
            symbol=self._to_mexc_symbol_repr(order.symbol),
            type=pydash.kebab_case(order.order_type.value).upper(),
            quantity=order.amount,
            price=order.price,
            stop_price=order.stop_price,
        )
        mexc_order = await self._mexc_remote_service.create_order(create_order_obj, client=client)
        symbol_config = await self._get_single_mexc_exchange_symbol_config(symbol=mexc_order.symbol, client=client)
        ret = self._map_mexc_order(mexc_order, symbol_config)
        return ret

    @override
    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        await self._mexc_remote_service.cancel_order_by_id(order_id=id, client=client)

    @override
    async def fetch_ohlcv(
        self, symbol: str, timeframe: "Timeframe", limit: int = 251, *, client: Any | None = None
    ) -> list[list[Any]]:
        return await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe, limit, exchange=self._exchange)

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

    async def _get_single_mexc_exchange_symbol_config(
        self, symbol: str, *, client: Any | None = None
    ) -> MEXCExchangeSymbolConfigDto:
        mexc_exchange_symbol_config_dict = await self._get_all_mexc_exchange_symbol_config(client=client)
        ret = mexc_exchange_symbol_config_dict[symbol]
        return ret

    async def _get_all_mexc_exchange_symbol_config(
        self, *, client: Any | None = None
    ) -> dict[str, MEXCExchangeSymbolConfigDto]:
        exchange_info = await self._mexc_remote_service.get_exchange_info(client=client)
        return {symbol_info.symbol: symbol_info for symbol_info in exchange_info.symbols}

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

    def _map_mexc_order(self, mexc_order: MEXCOrderDto, symbol_config: MEXCExchangeSymbolConfigDto) -> Order:
        ret = Order(
            id=mexc_order.order_id,
            created_at=datetime.fromtimestamp(mexc_order.time, UTC),
            symbol=f"{symbol_config.base_asset}/{symbol_config.quote_asset}",
            order_type=OrderTypeEnum(pydash.snake_case(mexc_order.type).upper()),
            side=OrderSideEnum(mexc_order.side.upper()),
            amount=float(mexc_order.executed_qty),
            status=self._map_mexc_status(mexc_order.status),
            price=float(mexc_order.price) if mexc_order.price else None,
            stop_price=float(mexc_order.stop_price) if mexc_order.stop_price else None,
        )
        return ret

    def _map_mexc_trade(self, mexc_trade: MEXCTradeDto, symbol_config: MEXCExchangeSymbolConfigDto) -> Trade:
        ret = Trade(
            id=mexc_trade.id,
            order_id=mexc_trade.order_id,
            symbol=f"{symbol_config.base_asset}/{symbol_config.quote_asset}",
            side=OrderSideEnum(mexc_trade.side.upper()),
            price=mexc_trade.price,
            amount=mexc_trade.qty,
            fee_amount=mexc_trade.commission,
        )
        return ret

    def _map_mexc_status(mexc_status: MEXCOrderStatus) -> OrderStatusEnum:
        match mexc_status:
            case "NEW":
                ret = OrderStatusEnum.OPEN
            case "FILLED":
                ret = OrderStatusEnum.FILLED
            case "PARTIALLY_FILLED":
                ret = OrderStatusEnum.PARTIALLY_FILLED
            case "CANCELED":
                ret = OrderStatusEnum.CANCELLED
            case "PARTIALLY_CANCELED":
                ret = OrderStatusEnum.PARTIALLY_CANCELLED
            case _:
                raise ValueError(f"Unknown MEXC order status: {mexc_status}")
        return ret

    def _to_mexc_symbol_repr(self, symbol: str) -> str:
        ret = "".join(symbol.split("/"))
        return ret
