import logging
from typing import override

from aiogram import html
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTradingTaskService

logger = logging.getLogger(__name__)


class LimitSellOrderGuardTaskService(AbstractTradingTaskService):
    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD

    @override
    async def _run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            sell_orders = await self._bit2me_remote_service.get_pending_sell_orders(client=client)
            if sell_orders:
                await self._handle_opened_sell_orders(sell_orders, client=client)
            else:  # pragma: no cover
                logger.info("There are no opened limit sell orders to handle! Let's see in the upcoming executions...")

    @override
    def _get_job_trigger(self) -> IntervalTrigger:
        return IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)

    async def _handle_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> None:
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = await self._fetch_tickers_for_open_sell_orders(
            opened_sell_orders, client=client
        )
        previous_used_buy_trade_ids: set[str] = set()
        for sell_order in opened_sell_orders:
            try:
                previous_used_buy_trade_ids, *_ = await self._handle_single_sell_order(
                    sell_order, current_tickers_by_symbol, previous_used_buy_trade_ids, client=client
                )
            except Exception as e:
                logger.error(str(e), exc_info=True)
                await self._notify_fatal_error_via_telegram(e)

    async def _handle_single_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        previous_used_buy_trade_ids: set[str],
        *,
        client: AsyncClient,
    ) -> set[str]:
        *_, fiat_currency = sell_order.symbol.split("/")
        (
            avg_buy_price,
            previous_used_buy_trade_ids,
        ) = await self._orders_analytics_service.calculate_correlated_avg_buy_price(
            sell_order, previous_used_buy_trade_ids, client=client
        )
        (safeguard_stop_price, *_) = await self._orders_analytics_service.calculate_safeguard_stop_price(
            sell_order, avg_buy_price
        )
        logger.info(
            f"Supervising {sell_order.order_type.upper()} SELL order {repr(sell_order)}: "
            + f"Avg Buy Price = {avg_buy_price} {fiat_currency} / "
            + f"Safeguard Stop Price = {safeguard_stop_price} {fiat_currency}"
        )
        tickers = current_tickers_by_symbol[sell_order.symbol]
        if tickers.close <= safeguard_stop_price:
            # Cancel current take-profit sell limit order
            await self._bit2me_remote_service.cancel_order_by_id(sell_order.id, client=client)
            new_market_order = await self._bit2me_remote_service.create_order(
                order=CreateNewBit2MeOrderDto(
                    order_type="market",
                    side=sell_order.side,
                    symbol=sell_order.symbol,
                    amount=str(sell_order.order_amount),
                ),
                client=client,
            )
            logger.info(f"[NEW MARKET ORDER] Id: '{new_market_order.id}', for selling everything immediately!")
            await self._notify_new_market_order_created_via_telegram(
                new_market_order, current_symbol_price=tickers.close, safeguard_stop_price=safeguard_stop_price
            )
        return (previous_used_buy_trade_ids,)

    async def _notify_new_market_order_created_via_telegram(
        self, new_market_order: Bit2MeOrderDto, *, current_symbol_price: float | int, safeguard_stop_price: float | int
    ) -> None:
        try:
            crypto_currency, fiat_currency = new_market_order.symbol.split("/")
            telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
                notification_type=PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT
            )
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(
                    chat_id=tg_chat_id,
                    text=f"🚨🚨 {html.bold('Market sell FILLED!')} {new_market_order.order_amount} {crypto_currency} sold "  # noqa: E501
                    + f"due to current {crypto_currency} price ({current_symbol_price} {fiat_currency}) "
                    + f"is lower than the safeguard calculated ({safeguard_stop_price} {fiat_currency})!!",
                )
        except Exception as e:  # pragma: no cover
            logger.warning(f"Unexpected error, notifying fatal error via Telegram: {str(e)}", exc_info=True)
