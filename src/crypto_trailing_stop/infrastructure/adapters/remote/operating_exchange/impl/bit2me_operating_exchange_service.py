from enum import Enum
from typing import TYPE_CHECKING, Any, override

import pydash

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
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


class Bit2MeOperatingExchangeService(AbstractOperatingExchangeService):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        super().__init__()
        self._bit2me_remote_service = bit2me_remote_service

    @override
    async def get_account_info(self, *, client: Any | None = None) -> AccountInfo:
        bit2me_account_info = await self._bit2me_remote_service.get_account_info(client=client)
        return AccountInfo(
            registration_date=bit2me_account_info.registration_date,
            currency_code=bit2me_account_info.profile.currency_code,
        )

    @override
    async def get_trading_wallet_balances(
        self, symbols: list[str] | str | None = None, *, client: Any | None = None
    ) -> list[TradingWalletBalance]:
        bit2me_wallet_balances = await self._bit2me_remote_service.get_trading_wallet_balances(
            symbols=symbols, client=client
        )
        return [
            TradingWalletBalance(
                currency=wallet_balance.currency,
                balance=wallet_balance.balance,
                blocked_balance=wallet_balance.blocked_balance,
            )
            for wallet_balance in bit2me_wallet_balances
        ]

    @override
    async def retrieve_porfolio_balance(self, user_currency: str, *, client: Any | None = None) -> PortfolioBalance:
        bit2me_portfolio_balances = await self._bit2me_remote_service.retrieve_porfolio_balance(
            user_currency=user_currency.lower(), client=client
        )
        balances_by_service_name = pydash.group_by(bit2me_portfolio_balances, lambda b: b.service_name)
        total_balance = round(
            pydash.sum_(
                [
                    current_balance.total.converted_balance.value
                    for current_balance in balances_by_service_name.get("all", [])
                ]
            ),
            ndigits=2,
        )
        return PortfolioBalance(total_balance=total_balance)

    @override
    async def get_single_tickers_by_symbol(self, symbol: str, *, client: Any | None = None) -> SymbolTickers:
        bit2me_tickers = await self._bit2me_remote_service.get_single_tickers_by_symbol(symbol=symbol, client=client)
        ret = SymbolTickers(
            timestamp=bit2me_tickers.timestamp,
            symbol=bit2me_tickers.symbol,
            close=bit2me_tickers.close,
            bid=bit2me_tickers.bid,
            ask=bit2me_tickers.ask,
        )
        return ret

    @override
    async def get_tickers_by_symbols(
        self, symbols: list[str] | str = [], *, client: Any | None = None
    ) -> list[SymbolTickers]:
        bit2me_tickers_list = await self._bit2me_remote_service.get_tickers_by_symbols(symbols=symbols, client=client)
        return [
            SymbolTickers(
                timestamp=tickers.timestamp,
                symbol=tickers.symbol,
                close=tickers.close,
                bid=tickers.bid,
                ask=tickers.ask,
            )
            for tickers in bit2me_tickers_list
        ]

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
        bit2me_orders = await self._bit2me_remote_service.get_orders(
            side=side, order_type=order_type, status=status, symbol=symbol, client=client
        )
        return [self._map_bit2me_order(bit2me_order) for bit2me_order in bit2me_orders]

    @override
    async def get_order_by_id(self, id: str, *, client: Any | None = None) -> Order | None:
        bit2me_order = await self._bit2me_remote_service.get_order_by_id(id=id, client=client)
        return self._map_bit2me_order(bit2me_order) if bit2me_order else None

    @override
    async def get_trades(
        self, *, side: OrderSideEnum | None = None, symbol: str | None = None, client: Any | None = None
    ) -> list[Trade]:
        bit2me_trades = await self._bit2me_remote_service.get_trades(side=side, symbol=symbol, client=client)
        return [
            Trade(
                id=trade.id,
                order_id=trade.order_id,
                symbol=trade.symbol,
                side=OrderSideEnum(trade.side.value if isinstance(trade.side, Enum) else str(trade.side)),
                price=trade.price,
                amount=trade.amount,
                fee_amount=trade.fee_amount,
            )
            for trade in bit2me_trades
        ]

    @override
    async def fetch_ohlcv(
        self, symbol: str, timeframe: "Timeframe", limit: int = 251, *, client: Any | None = None
    ) -> list[list[Any]]:
        return await self._bit2me_remote_service.fetch_ohlcv(
            symbol=symbol, timeframe=timeframe, limit=limit, client=client
        )

    @override
    async def get_trading_market_config_by_symbol(
        self, symbol: str, *, client: Any | None = None
    ) -> SymbolMarketConfig:
        bit2me_market_config = await self._bit2me_remote_service.get_trading_market_config_by_symbol(
            symbol=symbol, client=client
        )
        return self._map_market_config(bit2me_market_config)

    @override
    async def get_trading_market_config_list(self, *, client: Any | None = None) -> dict[str, SymbolMarketConfig]:
        bit2me_market_config_list = await self._bit2me_remote_service.get_trading_market_config_list(client=client)
        return {
            market_config.symbol: self._map_market_config(market_config) for market_config in bit2me_market_config_list
        }

    @override
    async def create_order(self, order: Order, *, client: Any | None = None) -> Order:
        create_new_bit2me_order = CreateNewBit2MeOrderDto(
            order_type=order.order_type.value if isinstance(order.order_type, Enum) else str(order.order_type),
            side=order.side.value if isinstance(order.side, Enum) else str(order.side),
            symbol=order.symbol,
            price=str(order.price) if order.price else None,
            amount=str(order.amount) if order.amount else None,
            stop_price=str(order.stop_price) if order.stop_price else None,
        )
        bit2me_order = await self._bit2me_remote_service.create_order(create_new_bit2me_order, client=client)
        ret = self._map_bit2me_order(bit2me_order)
        return ret

    @override
    async def cancel_order_by_id(self, id: str, *, client: Any | None = None) -> None:
        await self._bit2me_remote_service.cancel_order_by_id(id=id, client=client)

    @override
    async def get_client(self) -> Any:
        return await self._bit2me_remote_service.get_http_client()

    def _map_bit2me_order(self, bit2me_order: Bit2MeOrderDto) -> Order:
        return Order(
            id=bit2me_order.id,
            symbol=bit2me_order.symbol,
            created_at=bit2me_order.created_at,
            order_type=OrderTypeEnum(
                bit2me_order.order_type.value
                if isinstance(bit2me_order.order_type, Enum)
                else str(bit2me_order.order_type)
            ),
            status=OrderStatusEnum(
                bit2me_order.status.value if isinstance(bit2me_order.status, Enum) else str(bit2me_order.status)
            ),
            side=OrderSideEnum(
                bit2me_order.side.value if isinstance(bit2me_order.side, Enum) else str(bit2me_order.side)
            ),
            amount=bit2me_order.order_amount,
            stop_price=bit2me_order.stop_price,
            price=bit2me_order.price,
        )

    def _map_market_config(self, bit2me_market_config: Bit2MeMarketConfigDto) -> SymbolMarketConfig:
        return SymbolMarketConfig(
            symbol=bit2me_market_config.symbol,
            price_precision=bit2me_market_config.price_precision,
            amount_precision=bit2me_market_config.amount_precision,
        )
