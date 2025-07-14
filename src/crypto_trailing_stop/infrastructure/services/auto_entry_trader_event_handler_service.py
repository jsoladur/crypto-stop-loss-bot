import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import override

import numpy as np
from aiogram import html
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    DEFAULT_NUMBER_OF_DECIMALS_IN_QUANTITY,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    NUMBER_OF_DECIMALS_IN_QUANTITY_BY_SYMBOL,
    STOP_LOSS_STEPS_VALUE_LIST,
    TRIGGER_BUY_ACTION_EVENT_NAME,
)
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
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
        self._crypto_analytics_service = CryptoAnalyticsService(bit2me_remote_service=self._bit2me_remote_service)
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            stop_loss_percent_service=self._stop_loss_percent_service,
            crypto_analytics_service=self._crypto_analytics_service,
        )
        self._auto_buy_trader_config_service = AutoBuyTraderConfigService(
            bit2me_remote_service=self._bit2me_remote_service
        )

    @override
    def configure(self) -> None:
        event_emitter = get_event_emitter()
        event_emitter.add_listener(TRIGGER_BUY_ACTION_EVENT_NAME, self.on_buy_market_signal)

    async def trigger_immediate_buy_market_signal(self, symbol: str) -> None:
        crypto_market_metrics = await self._crypto_analytics_service.get_crypto_market_metrics(
            symbol, over_candlestick=CandleStickEnum.LAST
        )
        market_signal_item = MarketSignalItem(
            timestamp=datetime.now(UTC),
            symbol=crypto_market_metrics.symbol,
            timeframe="1h",
            signal_type="buy",
            rsi_state=crypto_market_metrics.rsi_state,
            atr=crypto_market_metrics.atr,
            closing_price=crypto_market_metrics.closing_price,
            ema_long_price=crypto_market_metrics.ema_long,
        )
        event_emitter = get_event_emitter()
        event_emitter.emit(TRIGGER_BUY_ACTION_EVENT_NAME, market_signal_item)

    async def on_buy_market_signal(self, market_signal_item: MarketSignalItem) -> None:
        try:
            is_enabled_for = await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_ENTRY_TRADER)
            if is_enabled_for:
                crypto_currency, fiat_currency = market_signal_item.symbol.split("/")
                buy_trader_config = await self._auto_buy_trader_config_service.find_by_symbol(crypto_currency)
                if buy_trader_config.fiat_wallet_percent_assigned > 0:
                    if market_signal_item.atr_percent < self._configuration_properties.max_atr_percent_for_auto_entry:
                        await self._perform_trading(
                            market_signal_item, crypto_currency, fiat_currency, buy_trader_config
                        )
                    else:
                        reason_message = "    - 🎢 " + html.italic(
                            f"Current ATR ({market_signal_item.atr_percent:.2f}%) "
                            + f"exceeds the allowed risk threshold (&lt;={self._configuration_properties.max_atr_percent_for_auto_entry}%).\n"  # noqa: E501
                        )
                        reason_message += "⏸️ Trading paused to protect capital."
                        await self._notify_warning(market_signal_item, warning_reason_message=reason_message)
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
            initial_amount_to_invest = await self._calculate_total_amount_to_invest(
                buy_trader_config, fiat_currency, client
            )
            # XXX: [JMSOLA] Investing less than 25.0 EUR is not worthly
            if initial_amount_to_invest > AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST:
                await self._invest(
                    market_signal_item, crypto_currency, fiat_currency, initial_amount_to_invest, client=client
                )
            else:
                reason_message = "    - 💸 " + html.italic(
                    f"Insufficient funds to invest ({initial_amount_to_invest:.2f} {fiat_currency}). "
                    + f"Minimal funds needed are {AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST:.2f} {fiat_currency}"
                )
                await self._notify_warning(market_signal_item, warning_reason_message=reason_message)

    async def _invest(
        self,
        market_signal_item: MarketSignalItem,
        crypto_currency: str,
        fiat_currency: str,
        initial_amount_to_invest: float,
        *,
        client: AsyncClient,
    ) -> None:
        # XXX: [JMSOLA] Get the current tickers.close price for calculate the order_amount
        tickers = await self._bit2me_remote_service.get_tickers_by_symbol(market_signal_item.symbol)
        # XXX: [JMSOLA] Calculate buy order amount

        buy_order_amount = self._floor_round(
            initial_amount_to_invest / tickers.close,
            ndigits=NUMBER_OF_DECIMALS_IN_QUANTITY_BY_SYMBOL.get(
                market_signal_item.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_QUANTITY
            ),
        )
        final_amount_to_invest = buy_order_amount * tickers.close
        logger.info(
            f"[Auto-Entry Trader] Trying to create BUY MARKET ORDER for {market_signal_item.symbol}, "  # noqa: E501
            + f"which has current price {tickers.close} {fiat_currency}. "
            + f"Investing {final_amount_to_invest:.2f} {fiat_currency}, "
            + f"buying {buy_order_amount} {crypto_currency}"
        )
        new_buy_market_order = await self._create_new_buy_market_order_and_wait_until_filled(
            market_signal_item, buy_order_amount, client=client
        )
        # XXX [JMSOLA]: Disabling temporary Limit Sell Guard order for precaution
        await self._global_flag_service.force_disable_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)
        # Creating new sell limite order
        new_limit_sell_order = await self._create_new_sell_limit_order(
            new_buy_market_order, tickers, crypto_currency, client=client
        )
        guard_metrics, stop_loss_percent_value = await self._update_stop_loss(
            new_limit_sell_order, crypto_currency, client=client
        )
        # Ensure Auto-exit on sudden SELL 1H signal is enabled
        if not (await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_EXIT_SELL_1H)):
            await self._global_flag_service.toggle_by_name(GlobalFlagTypeEnum.AUTO_EXIT_SELL_1H)
        # Re-enable Limit Sell Order Guard, once stop loss is setup!
        await self._global_flag_service.toggle_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)
        # Notifying via Telegram
        await self._notify_success_alert(
            new_buy_market_order, new_limit_sell_order, tickers, guard_metrics, stop_loss_percent_value
        )

    async def _calculate_total_amount_to_invest(
        self, buy_trader_config: AutoBuyTraderConfigItem, fiat_currency: str, client: AsyncClient
    ) -> float | int:
        fiat_wallet_assigned_decimal_value = buy_trader_config.fiat_wallet_percent_assigned / 100.0
        # 1.) Call to GlobalSummaryService.calculate_portfolio_total_fiat_amount(..),
        # to get total portfolio AMOUNT
        total_portfolio_fiat_amount = await self._global_summary_service.calculate_portfolio_total_fiat_amount(
            fiat_currency, client=client
        )
        portfolio_assigned_amount = math.floor(total_portfolio_fiat_amount * fiat_wallet_assigned_decimal_value)
        eur_wallet_balance, *_ = await self._bit2me_remote_service.get_trading_wallet_balance(
            symbols=fiat_currency.upper(), client=client
        )
        amount_to_invest = min(math.floor(eur_wallet_balance.balance), portfolio_assigned_amount)
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
            await asyncio.sleep(delay=2.0)
            new_buy_market_order = await self._bit2me_remote_service.get_order_by_id(
                new_buy_market_order.id, client=client
            )

        return new_buy_market_order

    async def _create_new_sell_limit_order(
        self,
        new_buy_market_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        crypto_currency: str,
        *,
        client: AsyncClient,
    ) -> Bit2MeOrderDto:
        # # XXX [JMSOLA]: Once buy sell order is FILLED,
        # we are now creating a LIMIT SELL ORDER to pass
        # the responsibility to the Limit Sell Order Guard for selling,
        # at some further favorable point!
        crypto_currency_wallet, *_ = await self._bit2me_remote_service.get_trading_wallet_balance(
            symbols=crypto_currency, client=client
        )
        new_limit_sell_order_amount = self._floor_round(
            min(crypto_currency_wallet.balance, new_buy_market_order.order_amount),
            ndigits=NUMBER_OF_DECIMALS_IN_QUANTITY_BY_SYMBOL.get(
                new_buy_market_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_QUANTITY
            ),
        )
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
                        ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                            new_buy_market_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
                        ),
                    )
                ),
                amount=str(new_limit_sell_order_amount),
            ),
            client=client,
        )
        return new_limit_sell_order

    async def _update_stop_loss(
        self, new_limit_sell_order: Bit2MeOrderDto, crypto_currency: str, *, client: AsyncClient
    ) -> tuple[LimitSellOrderGuardMetrics, float]:
        guard_metrics, *_ = await self._orders_analytics_service.calculate_guard_metrics_by_sell_order(
            new_limit_sell_order, client=client
        )
        # XXX [JMSOLA]: Calculate suggested stop loss and update it
        steps = np.array(STOP_LOSS_STEPS_VALUE_LIST)
        stop_loss_percent_value = float(steps[steps >= guard_metrics.suggested_stop_loss_percent_value].min())
        await self._stop_loss_percent_service.save_or_update(
            StopLossPercentItem(symbol=crypto_currency, value=stop_loss_percent_value)
        )
        return guard_metrics, stop_loss_percent_value

    async def _notify_warning(self, market_signal_item: MarketSignalItem, warning_reason_message: str) -> None:
        message = f"⚠️ {html.bold('AUTO-ENTRY TRADER WARNING')} ⚠️\n\n"
        message += f"Stopping trading operations for {market_signal_item.symbol}, despite recent BUY 1H signal.\n"  # noqa: E501
        message += "✴️ Reasons:\n"
        message += warning_reason_message
        await self._notify_alert_by_type(PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT, message)

    async def _notify_success_alert(
        self,
        new_buy_market_order: Bit2MeOrderDto,
        new_limit_sell_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        stop_loss_percent_value: float,
    ) -> None:
        is_enabled_for_auto_exit_atr_take_profit = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT
        )

        crypto_currency, fiat_currency = tickers.symbol.split("/")
        message = f"✅ {html.bold('MARKET BUY ORDER FILLED')} ✅\n\n"
        message += (
            f"🔥 {new_buy_market_order.order_amount} {crypto_currency} "
            + f"purchased at {tickers.close:.2f} {fiat_currency}"
        )
        message += html.bold("\n\n⚠️ IMPORTANT CONSIDERATIONS ⚠️\n\n")
        new_limit_sell_order_price_formatted = f"{new_limit_sell_order.price:.2f} {fiat_currency}"
        message += (
            f"* 🚀 A new {html.bold(new_limit_sell_order.order_type.upper() + ' Sell Order')} ("
            + f"{new_limit_sell_order.order_amount:.2f} {crypto_currency}), "
            + f"further sell at {html.bold(new_limit_sell_order_price_formatted)}"
            + " has been CREATED to start looking at possible SELL ACTION 🤑\n"
        )
        message += f"* 🚏 {html.bold('Stop Loss')} has been setup to {stop_loss_percent_value}%\n"
        message += f"* 🛡️ {html.bold('Safeguard Stop Price = ' + str(guard_metrics.safeguard_stop_price) + ' ' + fiat_currency)}\n"  # noqa: E501
        if is_enabled_for_auto_exit_atr_take_profit:
            message += f"* 🎯 {html.bold('ATR Take Profit Price')} = {guard_metrics.suggested_take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
        message += f"* 🔰 {html.bold(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD.description)} has been ENABLED!\n"
        message += f"* 🛑 {html.bold(GlobalFlagTypeEnum.AUTO_EXIT_SELL_1H.description)} has been ENABLED!\n"
        if is_enabled_for_auto_exit_atr_take_profit:
            message += f"* ⚡ {html.bold(GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT.description)} is ENABLED!"
        else:
            message += (
                f"* ⚡ {html.bold(GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT.description)} is DISABLED! "
                + "Please, consider to enable it if needed!"
            )
        await self._notify_alert_by_type(PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT, message)

    def _floor_round(self, value: float, *, ndigits: int) -> float:
        factor = 10**ndigits
        return math.floor(value * factor) / factor
