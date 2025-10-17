from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

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


class AbstractOperatingExchangeService(ABC):
    async def get_pending_sell_orders(
        self, *, order_type: OrderTypeEnum | None = None, client: Any | None = None
    ) -> list[Order]:
        """Fetches pending sell orders from the exchange.

        Args:
            order_type (OrderTypeEnum | None, optional): The type of orders to fetch. Defaults to None.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[Order]: A list of pending sell orders.
        """
        return await self.get_orders(
            side=OrderSideEnum.SELL,
            status=[OrderStatusEnum.OPEN, OrderStatusEnum.INACTIVE],
            order_type=order_type,
            client=client,
        )

    async def get_pending_buy_orders(
        self, *, order_type: OrderTypeEnum | None = None, client: Any | None = None
    ) -> list[Order]:
        """Fetches pending buy orders from the exchange.

        Args:
            order_type (OrderTypeEnum | None, optional): The type of orders to fetch. Defaults to None.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[Order]: A list of pending buy orders.
        """
        return await self.get_orders(
            side=OrderSideEnum.BUY,
            status=[OrderStatusEnum.OPEN, OrderStatusEnum.INACTIVE],
            order_type=order_type,
            client=client,
        )

    @abstractmethod
    async def get_account_info(self, *, client: Any | None = None) -> AccountInfo:
        """Fetches account information from the exchange.

        Args:
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            AccountInfo: An object containing account information.
        """

    @abstractmethod
    async def get_trading_wallet_balances(
        self, symbols: list[str] | str | None = None, *, client: Any | None = None
    ) -> list[TradingWalletBalance]:
        """Fetches trading wallet balances from the exchange.

        Args:
            symbols (list[str] | str | None, optional): A list of symbols to filter balances. Defaults to None.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[TradingWalletBalance]: A list of trading wallet balances.
        """

    @abstractmethod
    async def retrieve_porfolio_balance(self, user_currency: str, *, client: Any | None = None) -> PortfolioBalance:
        """Retrieves portfolio balance from the exchange.

        Args:
            user_currency (str): The user's preferred currency for balance representation.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            PortfolioBalance: An object containing portfolio balance information.
        """

    @abstractmethod
    async def get_single_tickers_by_symbol(self, symbol: str, *, client: Any | None = None) -> SymbolTickers:
        """Fetches ticker information for a single symbol from the exchange.

        Args:
            symbol (str): The symbol to fetch ticker information for.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            SymbolTickers: An object containing ticker information for the symbol.
        """

    @abstractmethod
    async def get_tickers_by_symbols(
        self, symbols: list[str] | str = [], *, client: Any | None = None
    ) -> list[SymbolTickers]:
        """Fetches ticker information for multiple symbols from the exchange.

        Args:
            symbols (list[str] | str, optional): A list of symbols to fetch ticker information for. Defaults to [].
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[SymbolTickers]: A list of objects containing ticker information for the symbols.
        """

    @abstractmethod
    async def get_orders(
        self,
        *,
        side: OrderSideEnum | None = None,
        order_type: OrderTypeEnum | None = None,
        status: list[OrderStatusEnum] | OrderStatusEnum | None = None,
        symbol: str | None = None,
        client: Any | None = None,
    ) -> list[Order]:
        """Fetches orders from the exchange based on various filters.

        Args:
            side (OrderSideEnum | None, optional): The side of the orders to fetch (buy/sell). Defaults to None.
            order_type (OrderTypeEnum | None, optional): The type of orders to fetch. Defaults to None.
            status (list[OrderStatusEnum] | OrderStatusEnum | None, optional): The status of the orders to fetch. Defaults to None.
            symbol (str | None, optional): The symbol to filter orders by. Defaults to None.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[Order]: A list of orders matching the provided filters.
        """  # noqa: E501

    @abstractmethod
    async def get_order_by_id(self, id: str, *, client: Any | None = None) -> Order | None:
        """Fetches a specific order by its ID from the exchange.

        Args:
            id (str): The ID of the order to fetch.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            Order | None: An order object if found, otherwise None.
        """

    @abstractmethod
    async def get_trades(
        self, *, side: OrderSideEnum | None = None, symbol: str | None = None, client: Any | None = None
    ) -> list[Trade]:
        """Fetches trades from the exchange based on various filters.

        Args:
            side (OrderSideEnum | None, optional): The side of the trades to fetch (buy/sell). Defaults to None.
            symbol (str | None, optional): The symbol to filter trades by. Defaults to None.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[Trade]: A list of trades matching the provided filters.
        """

    @abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, timeframe: "Timeframe", limit: int = 251, *, client: Any | None = None
    ) -> list[list[Any]]:
        """Fetches OHLCV (Open, High, Low, Close, Volume) data for a given symbol and timeframe.

        Args:
            symbol (str): The trading pair symbol (e.g., 'BTC/USD').
            timeframe (Timeframe): The timeframe for the OHLCV data.
            limit (int, optional): The maximum number of data points to fetch. Defaults to 251.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            list[list[Any]]: A list of OHLCV data points.
        """

    @abstractmethod
    async def get_trading_market_config_by_symbol(
        self, symbol: str, *, client: Any | None = None
    ) -> SymbolMarketConfig | None:
        """Fetches trading market configuration for a given symbol.

        Args:
            symbol (str): The trading pair symbol (e.g., 'BTC/USD').
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            SymbolMarketConfig | None: A SymbolMarketConfig object if found, otherwise None.
        """

    @abstractmethod
    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        """Fetches trading market configurations for all symbols.

        Args:
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            dict[str, SymbolMarketConfig]: A dictionary of trading market configurations.
        """

    @abstractmethod
    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        """Creates a new order on the exchange.

        Args:
            order (Order): The order object containing order details.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            Order: The created order object with updated details from the exchange.
        """

    @abstractmethod
    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        """Cancels an order by its ID on the exchange.

        Args:
            id (str): The ID of the order to cancel.
            client (Any | None, optional): Client to connect with the exchange. Defaults to None.

        Returns:
            None
        """

    @abstractmethod
    async def get_client(self) -> Any:
        """Creates and returns a client to connect with the exchange.

        Returns:
            Any: A client object for the exchange.
        """

    @abstractmethod
    def get_operating_exchange(self) -> OperatingExchangeEnum:
        """Returns the operating exchange enum value.

        Returns:
            OperatingExchangeEnum: The operating exchange enum.
        """
