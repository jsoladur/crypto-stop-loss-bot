import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Literal

from coinbase.rest import RESTClient
from pandas import Timedelta

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_account_info_dto import CoinbaseAccountInfoDto
from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_order_dto import (
    CoinbaseOrderDto,
    CoinbaseOrderSide,
    CoinbaseOrderStatus,
    CoinbaseOrderType,
    CreateNewCoinbaseOrderDto,
)

from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_portfolio_balance_dto import CoinbasePortfolioBalanceDto
from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_tickers_dto import CoinbaseTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_trade_dto import CoinbaseTradeDto, CoinbaseTradeSide
from crypto_trailing_stop.infrastructure.adapters.dtos.coinbase_trading_wallet_balance import (
    CoinbaseTradingWalletBalanceDto,
)

logger = logging.getLogger(__name__)


class CoinbaseRemoteService:
    __metaclass__ = SingletonMeta

    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._client = RESTClient(
            api_key=self._configuration_properties.coinbase_api_key,
            api_secret=self._configuration_properties.coinbase_api_secret,
            timeout=5
        )

    async def get_favourite_crypto_currencies(self) -> list[str]:
        products = self._client.get_products()
        return [product.base_display_symbol for product in products.products if product.is_watchlisted]

    async def get_account_info(self) -> CoinbaseAccountInfoDto:
        accounts = self._client.get_accounts()
        return CoinbaseAccountInfoDto.model_validate(accounts.model_dump())

    async def get_trading_wallet_balances(
        self, symbols: list[str] | str | None = None
    ) -> list[CoinbaseTradingWalletBalanceDto]:
        accounts = self._client.get_accounts()
        balances = accounts.accounts
        if symbols:
            symbol_list = [symbols] if isinstance(symbols, str) else symbols
            balances = [b for b in balances if b.currency in symbol_list]
        return [CoinbaseTradingWalletBalanceDto.model_validate(b.model_dump()) for b in balances]

    async def retrieve_porfolio_balance(
        self, user_currency: str
    ) -> list[CoinbasePortfolioBalanceDto]:
        accounts = self._client.get_accounts(currency=user_currency.strip().upper())
        return [CoinbasePortfolioBalanceDto.model_validate(account.model_dump()) for account in accounts.accounts]

    async def get_tickers_by_symbol(self, symbol: str) -> CoinbaseTickersDto | None:
        ticker = self._client.get_product_ticker(product_id=symbol)
        return CoinbaseTickersDto.model_validate(ticker.model_dump())

    async def get_pending_sell_orders(
        self, *, order_type: CoinbaseOrderType | None = None
    ) -> list[CoinbaseOrderDto]:
        return await self.get_orders(side="SELL", status=["OPEN", "PENDING"], order_type=order_type)

    async def get_pending_buy_orders(
        self, *, order_type: CoinbaseOrderType | None = None
    ) -> list[CoinbaseOrderDto]:
        return await self.get_orders(side="BUY", order_type=order_type, status=["OPEN", "PENDING"])

    async def get_orders(
        self,
        *,
        side: CoinbaseOrderSide | None = None,
        order_type: CoinbaseOrderType | None = None,
        status: list[CoinbaseOrderStatus] | CoinbaseOrderStatus | None = None,
        symbol: str | None = None
    ) -> list[CoinbaseOrderDto]:
        kwargs = {}
        if status:
            status_list = status if isinstance(status, (list, set, tuple, frozenset)) else [status]
            kwargs["order_status"] = ",".join([s.value if isinstance(s, Enum) else str(s) for s in status_list])
        if side:
            kwargs["order_side"] = side
        if order_type:
            kwargs["order_type"] = order_type
        if symbol:
            kwargs["product_id"] = symbol

        orders = self._client.get_historical_orders(**kwargs)
        return [CoinbaseOrderDto.model_validate(order.model_dump()) for order in orders.orders]

    async def get_order_by_id(self, id: str) -> CoinbaseOrderDto:
        order = self._client.get_historical_order(order_id=id)
        return CoinbaseOrderDto.model_validate(order.model_dump())

    async def get_trades(
        self, *, side: CoinbaseTradeSide | None = None, symbol: str | None = None
    ) -> list[CoinbaseTradeDto]:
        kwargs = {}
        if side:
            kwargs["order_side"] = side
        if symbol:
            kwargs["product_id"] = symbol

        fills = self._client.get_fills(**kwargs)
        return [CoinbaseTradeDto.model_validate(fill.model_dump()) for fill in fills.fills]

    async def create_order(
        self, order: CreateNewCoinbaseOrderDto
    ) -> CoinbaseOrderDto:
        order_dict = order.model_dump(mode="json", by_alias=True, exclude_none=True)
        if order.order_type == "MARKET":
            if order.side == "BUY":
                created_order = self._client.market_order_buy(
                    product_id=order_dict["product_id"],
                    quote_size=order_dict.get("quote_size") or str(float(order_dict["size"]) * float(order_dict["limit_price"])),
                    client_order_id=order_dict.get("client_order_id", "")
                )
            else:
                created_order = self._client.market_order_sell(
                    product_id=order_dict["product_id"],
                    base_size=order_dict["size"],
                    client_order_id=order_dict.get("client_order_id", "")
                )
        else:  # LIMIT order
            if order.side == "BUY":
                created_order = self._client.limit_order_buy(
                    product_id=order_dict["product_id"],
                    base_size=order_dict["size"],
                    limit_price=order_dict["limit_price"],
                    client_order_id=order_dict.get("client_order_id", "")
                )
            else:
                created_order = self._client.limit_order_sell(
                    product_id=order_dict["product_id"],
                    base_size=order_dict["size"],
                    limit_price=order_dict["limit_price"],
                    client_order_id=order_dict.get("client_order_id", "")
                )
        return CoinbaseOrderDto.model_validate(created_order.model_dump())

    async def cancel_order_by_id(self, id: str) -> None:
        self._client.cancel_orders([id])

    async def fetch_ohlcv(
        self, symbol: str, timeframe: Literal["4h", "1h", "30m"], limit: int = 251
    ) -> list[list[Any]]:
        granularity = self._convert_timeframe_to_granularity(timeframe)
        now = datetime.now(UTC)
        start_time = now - timedelta(minutes=limit * int(granularity))
        
        candles = self._client.get_product_candles(
            product_id=symbol,
            granularity=granularity,
            start=start_time.isoformat(),
            end=now.isoformat()
        )
        return [[c.start, c.open, c.high, c.low, c.close, c.volume] for c in candles.candles]

    def _convert_timeframe_to_granularity(self, timeframe: Literal["4h", "1h", "30m"]) -> str:
        # Coinbase granularity values in seconds: 60, 300, 900, 3600, 21600, 86400
        td = Timedelta(timeframe)
        seconds = int(td.total_seconds())
        return str(seconds)
