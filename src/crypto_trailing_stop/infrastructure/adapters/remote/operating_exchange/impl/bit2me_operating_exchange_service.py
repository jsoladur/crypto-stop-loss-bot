from typing import TYPE_CHECKING, Any

from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.base import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import (
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


class Bit2MeOperatingExchangeService(AbstractOperatingExchangeService, metaclass=SingletonABCMeta):
    def __init__(self):
        super().__init__()
        self._remote_service = Bit2MeRemoteService()

    async def get_favourite_crypto_currencies(self, *, client: Any | None = None) -> list[str]:
        raise NotImplementedError()

    async def get_account_info(self, *, client: Any | None = None) -> AccountInfo:
        raise NotImplementedError()

    async def get_trading_wallet_balances(
        self, symbols: list[str] | str | None = None, *, client: Any | None = None
    ) -> list[TradingWalletBalance]:
        raise NotImplementedError()

    async def retrieve_porfolio_balance(self, user_currency: str, *, client: Any | None = None) -> PortfolioBalance:
        raise NotImplementedError()

    async def get_single_tickers_by_symbol(self, symbol: str, *, client: Any | None = None) -> SymbolTickers:
        raise NotImplementedError()

    async def get_tickers_by_symbols(
        self, symbols: list[str] | str = [], *, client: Any | None = None
    ) -> list[SymbolTickers]:
        raise NotImplementedError()

    async def get_orders(
        self,
        *,
        side: OrderSideEnum | None = None,
        order_type: OrderTypeEnum | None = None,
        status: list[OrderStatusEnum] | OrderStatusEnum | None = None,
        symbol: str | None = None,
        client: Any | None = None,
    ) -> list[Order]:
        raise NotImplementedError()

    async def get_order_by_id(self, id: str, *, client: Any | None = None) -> Order | None:
        raise NotImplementedError()

    async def get_trades(
        self, *, side: OrderSideEnum | None = None, symbol: str | None = None, client: Any | None = None
    ) -> list[Trade]:
        raise NotImplementedError()

    async def fetch_ohlcv(
        self, symbol: str, timeframe: "Timeframe", limit: int = 251, *, client: Any | None = None
    ) -> list[list[Any]]:
        raise NotImplementedError()

    async def get_trading_market_config_by_symbol(
        self, symbol: str, *, client: Any | None = None
    ) -> SymbolMarketConfig | None:
        raise NotImplementedError()

    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        raise NotImplementedError()

    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        raise NotImplementedError()

    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        raise NotImplementedError()

    async def get_client(self) -> Any:
        raise NotImplementedError()
