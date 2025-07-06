import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
bit2me_remote_service = Bit2MeRemoteService()
stop_loss_percent_service = StopLossPercentService(
    bit2me_remote_service=bit2me_remote_service, global_flag_service=GlobalFlagService()
)
orders_analytics_service = OrdersAnalyticsService(
    bit2me_remote_service=bit2me_remote_service,
    stop_loss_percent_service=stop_loss_percent_service,
    crypto_analytics_service=CryptoAnalyticsService(
        bit2me_remote_service=bit2me_remote_service, ccxt_remote_service=CcxtRemoteService()
    ),
)


@dp.callback_query(F.data.regexp(r"^persist_stop_loss\$\$(.+?)\$\$(.+)$"))
async def handle_persist_stop_loss_callback(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^persist_stop_loss\$\$(.+?)\$\$(.+)$", callback_query.data)
            symbol = match.group(1).strip().upper()
            percent_value = float(match.group(2).strip())
            await stop_loss_percent_service.save_or_update(StopLossPercentItem(symbol=symbol, value=percent_value))
            answer_text = (
                f"ℹ Stop loss for {html.bold(symbol)} at {html.bold(str(percent_value) + '%')} "
                + "has been successfully stored and it will be applied right now! \n\n"
                + html.bold(
                    "⚠️ IMPORTANT NOTE: Limit Sell Order Guard Jobs has been DISABLED for PRECAUTION! "
                    + "Please, enable it after double-check everything out!"
                )
            )
            limit_sell_order_guard_metrics_list = (
                await orders_analytics_service.calculate_limit_sell_order_guard_metrics(symbol=symbol)
            )
            if limit_sell_order_guard_metrics_list:
                answer_text += f"\n\n🔨🔨{html.bold('Order Guard Metrics')} 🔨🔨\n\n"
                for idx, metrics in enumerate(limit_sell_order_guard_metrics_list):
                    crypto_currency, fiat_currency = metrics.sell_order.symbol.split("/")
                    answer_text += (
                        f"- 🚀 {html.bold(metrics.sell_order.order_type.upper() + ' Sell Order')} :: "
                        + f"💰 {metrics.sell_order.order_amount} {crypto_currency}, "  # noqa: E501
                        + f"further sell at {html.bold(str(metrics.sell_order.price) + ' ' + fiat_currency)}"
                    )
                    if metrics.sell_order.order_type == "stop-limit":
                        answer_text += (
                            " (when price reaches stop limit price at"
                            + f" {html.bold(str(metrics.sell_order.stop_price) + ' ' + fiat_currency)})"
                        )
                    answer_text += (
                        ":\n"
                        + f"    * 💳 {html.bold('Avg. Costs')} = {metrics.avg_buy_price} {fiat_currency}\n"
                        + f"    * 🚏 {html.bold('Stop Loss')} = {metrics.stop_loss_percent_value}%\n"
                        + f"    * 🛡️ {html.bold('Safeguard Stop Price = ' + str(metrics.safeguard_stop_price) + ' ' + fiat_currency)}"  # noqa: E501
                    )
                    answer_text += (
                        "\n📏 "
                        + html.bold("HINTS (ATR Volatility-based)")
                        + " 📏\n"
                        + f"    * 📏 {html.italic('Current ATR')} = ±{metrics.current_attr_value} {fiat_currency}\n"
                        + f"    * 🚏 {html.bold('Suggested Stop Loss')} = {metrics.suggested_stop_loss_percent_value}%\n"  # noqa: E501
                        + f"    * 💰 {html.bold('Suggested Safeguard Stop Price')} = {metrics.suggested_safeguard_stop_price} {fiat_currency}\n"  # noqa: E501
                        + f"    * 🎯 {html.bold('Suggested Take Profit Price')} = {metrics.suggested_take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
                    )
                    if idx + 1 < len(limit_sell_order_guard_metrics_list):
                        answer_text += "\n\n"
            await callback_query.message.answer(answer_text, reply_markup=keyboards_builder.get_home_keyboard())
        except Exception as e:
            logger.error(f"Error persisting stop loss: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while persisting a stop loss. Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
