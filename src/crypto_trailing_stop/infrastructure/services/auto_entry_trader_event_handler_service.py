import asyncio
import logging
import math
from typing import override

from aiogram import html
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    TRIGGER_BUY_ACTION_EVENT_NAME,
)
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem

logger = logging.getLogger(__name__)


class AutoEntryTraderEventHandlerService(AbstractService, metaclass=SingletonABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._global_flag_service = GlobalFlagService()
        self._stop_loss_percent_service = StopLossPercentService(
            bit2me_remote_service=self._bit2me_remote_service, global_flag_service=self._global_flag_service
        )
        self._global_summary_service = GlobalSummaryService(bit2me_remote_service=self._bit2me_remote_service)
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            stop_loss_percent_service=self._stop_loss_percent_service,
            crypto_analytics_service=CryptoAnalyticsService(
                bit2me_remote_service=self._bit2me_remote_service, ccxt_remote_service=CcxtRemoteService()
            ),
        )
        self._auto_buy_trader_config_service = AutoBuyTraderConfigService(
            bit2me_remote_service=self._bit2me_remote_service
        )

    @override
    def configure(self) -> None:
        event_emitter = get_event_emitter()
        event_emitter.add_listener(TRIGGER_BUY_ACTION_EVENT_NAME, self.on_buy_market_signal)

    async def on_buy_market_signal(self, market_signal_item: MarketSignalItem) -> None:
        try:
            is_enabled_for = await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_ENTRY_TRADER)
            if is_enabled_for:
                crypto_currency, fiat_currency = market_signal_item.symbol.split("/")
                buy_trader_config = await self._auto_buy_trader_config_service.find_by_symbol(crypto_currency)
                if buy_trader_config.fiat_wallet_percent_assigned > 0:
                    await self._perform_trading(market_signal_item, crypto_currency, fiat_currency, buy_trader_config)
        except Exception as e:
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    async def _perform_trading(
        self,
        market_signal_item: MarketSignalItem,
        crypto_currency: str,
        fiat_currency: str,
        buy_trader_config: AutoBuyTraderConfigItem,
    ) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            amount_to_invest = await self._calculate_total_amount_to_invest(buy_trader_config, client)
            # XXX: [JMSOLA] Investing less than 50.0 EUR is not worthly
            if amount_to_invest > AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST:
                # XXX: [JMSOLA] Get the current tickers.close price for calculate the order_amount
                tickers = await self._bit2me_remote_service.get_tickers_by_symbol(market_signal_item.symbol)
                # XXX: [JMSOLA] Calculate buy order amount
                number_of_digits_in_price = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                    market_signal_item.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
                )
                buy_order_amount = self._floor_round(
                    amount_to_invest / tickers.close, ndigits=number_of_digits_in_price
                )
                logger.info(
                    f"[Auto-Entry Trader] Trying to create BUY MARKET ORDER for {market_signal_item.symbol}, "  # noqa: E501
                    + f"which has current price {tickers.close} {fiat_currency}"
                    + f"Investing {amount_to_invest} {fiat_currency}, "
                    + f"buying {buy_order_amount} {crypto_currency}"
                )
                new_buy_market_order = await self._create_new_buy_market_order_and_wait_until_filled(
                    market_signal_item, buy_order_amount, client=client
                )
                # # XXX [JMSOLA]: Disabling temporary Limit Sell Guard order for precaution
                await self._global_flag_service.force_disable_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)

                # # XXX [JMSOLA]: Once buy sell order is FILLED,
                # we are now creating a LIMIT SELL ORDER to pass
                # the responsibility to the Limit Sell Order Guard for selling,
                # at some further favorable point!
                new_limit_sell_order = await self._bit2me_remote_service.create_order(
                    order=CreateNewBit2MeOrderDto(
                        order_type="limit",
                        side="sell",
                        symbol=new_buy_market_order.symbol,
                        price=str(
                            self._floor_round(
                                # XXX: [JMSOLA] Price is unreachable in purpose,
                                # for giving to the Limit Sell Order Guard the chance to
                                # operate properly
                                tickers.close * 2,
                                ndigits=number_of_digits_in_price,
                            )
                        ),
                        amount=str(new_buy_market_order.order_amount),
                    ),
                    client=client,
                )
                guard_metrics, *_ = await self._orders_analytics_service.calculate_guard_metrics_by_sell_order(
                    new_limit_sell_order, client=client
                )
                # XXX [JMSOLA]: Calculate suggested stop loss and update it
                # FIXME: Let's calculate the best based on 0.25% steps!!!
                await self._stop_loss_percent_service.save_or_update(
                    StopLossPercentItem(symbol=crypto_currency, value=guard_metrics.suggested_stop_loss_percent_value)
                )
                # Ensure Auto-exit on ATR-based take profit is enabled
                if not (await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT)):
                    await self._global_flag_service.toggle_by_name(GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT)
                # Re-enable Limit Sell Order Guard, once stop loss is setup!
                await self._global_flag_service.toggle_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)
                # FIXME: Improve this!!!
                await self._notify_alert(market_signal_item, body_message="IMPROVE THIS!!")

    async def _calculate_total_amount_to_invest(
        self, buy_trader_config: AutoBuyTraderConfigItem, client: AsyncClient
    ) -> float | int:
        fiat_wallet_assigned_decimal_value = buy_trader_config.fiat_wallet_percent_assigned / 100.0
        # 1.) Get account info # noqa: E501
        account_info = await self._bit2me_remote_service.get_account_info(client=client)
        # 1.) Call to GlobalSummaryService.calculate_portfolio_total_fiat_amount(..),
        # to get total portfolio AMOUNT
        total_portfolio_fiat_amount = await self._global_summary_service.calculate_portfolio_total_fiat_amount(
            account_info, client=client
        )
        portfolio_assigned_amount = math.floor(total_portfolio_fiat_amount * fiat_wallet_assigned_decimal_value)
        wallet_balance = await self._bit2me_remote_service.get_trading_wallet_balance(
            symbols=account_info.profile.currency_code.upper(), client=client
        )
        eur_wallet_balance, *_ = wallet_balance
        amount_to_invest = min(math.floor(eur_wallet_balance), portfolio_assigned_amount)
        return amount_to_invest

    async def _create_new_buy_market_order_and_wait_until_filled(
        self, market_signal_item: MarketSignalItem, buy_order_amount: float | int, client: AsyncClient
    ) -> Bit2MeOrderDto:
        new_buy_market_order: Bit2MeOrderDto = await self._bit2me_remote_service.create_order(
            order=CreateNewBit2MeOrderDto(
                order_type="market", side="buy", symbol=market_signal_item.symbol, amount=str(buy_order_amount)
            ),
            client=client,
        )
        while new_buy_market_order.status != "filled":
            logger.info(
                f"[Auto-Entry Trader] NEW MARKET ORDER Id: '{new_buy_market_order.id}'. "
                + "Waiting 2 seconds to watch the new buy market order is already filled..."
            )
            asyncio.sleep(delay=2.0)
            new_buy_market_order = await self._bit2me_remote_service.get_order_by_id(
                new_buy_market_order.id, client=client
            )

        return new_buy_market_order

    async def _notify_alert(self, market_signal_item: MarketSignalItem, body_message: str) -> None:
        telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
            notification_type=PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT
        )
        if telegram_chat_ids:
            tickers: Bit2MeTickersDto = await self._bit2me_remote_service.get_tickers_by_symbol(
                market_signal_item.symbol
            )
            crypto_currency, fiat_currency = tickers.symbol.split("/")
            message = f"✅✅ {html.bold('MARKET BUY ORDER CREATED')} ✅✅\n\n"
            message += f"{body_message}\n"
            message += html.bold(f"🔥 {crypto_currency} current price is {tickers.close} {fiat_currency}")
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)

    def _floor_round(self, value: float, *, ndigits: int) -> float:
        factor = 10**ndigits
        return math.floor(value * factor) / factor
