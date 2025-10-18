from typing import TYPE_CHECKING, Any, override

from crypto_trailing_stop.commons.constants import MEXC_TAKER_FEES
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
        # FIXME: To be implemented properly
        return PortfolioBalance(total_balance=0.0)

    @override
    async def get_accounting_summary_by_year(self, year: str, *, client: Any | None = None) -> bytes:
        raise NotImplementedError("To be implemented")

    @override
    async def get_single_tickers_by_symbol(self, symbol: str, *, client: Any | None = None) -> SymbolTickers:
        raise NotImplementedError("To be implemented")

    @override
    async def get_tickers_by_symbols(
        self, symbols: list[str] | str = [], *, client: Any | None = None
    ) -> list[SymbolTickers]:
        raise NotImplementedError("To be implemented")

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
    async def get_trading_crypto_currencies(self, *, client: Any | None = None) -> list[str]:
        raise NotImplementedError("To be implemented")

    @override
    async def get_trading_market_config_by_symbol(
        self, symbol: str, *, client: Any | None = None
    ) -> SymbolMarketConfig:
        raise NotImplementedError("To be implemented")

    @override
    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        raise NotImplementedError("To be implemented")

    @override
    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        raise NotImplementedError("To be implemented")

    @override
    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        raise NotImplementedError("To be implemented")

    @override
    async def get_client(self) -> Any:
        return await self._mexc_remote_service.get_http_client()

    @override
    def get_taker_fee(self) -> float:
        return MEXC_TAKER_FEES

    @override
    def get_operating_exchange(self) -> OperatingExchangeEnum:
        return OperatingExchangeEnum.MEXC
