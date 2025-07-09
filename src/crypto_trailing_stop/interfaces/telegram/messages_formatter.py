from zoneinfo import ZoneInfo

from aiogram import html

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.services.vo.current_crypto_metrics import CurrentCryptoMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem


class MessagesFormatter(metaclass=SingletonMeta):
    def format_current_prices_message(self, tickers_list: Bit2MeTickersDto) -> str:
        message_lines = ["===========================", "💵 CURRENT PRICES 💵", "==========================="]
        for tickers in tickers_list:
            crypto_currency, fiat_currency = tickers.symbol.split("/")
            message_lines.append(
                f"🔥 {html.bold(crypto_currency.upper())} 💰 {html.bold(str(tickers.close) + ' ' + fiat_currency)}"
            )
        ret = "\n".join(message_lines)
        return ret

    def format_current_crypto_metrics_message(self, metrics: CurrentCryptoMetrics) -> str:
        *_, fiat_currency = metrics.symbol.split("/")
        header = f"🧮 {html.bold('CURRENT METRICS')} for {html.bold(metrics.symbol)} 🧮\n\n"
        message_lines = [
            f"💰 {html.bold('Current Price')} = {html.code(f'{metrics.current_price:.2f} {fiat_currency}')}",
            f"📈 {html.bold('EMA Short')} = {metrics.ema_short:.2f} {fiat_currency}",
            f"📉 {html.bold('EMA Mid')} = {metrics.ema_mid:.2f} {fiat_currency}",
            f"📐 {html.bold('EMA Long')} = {metrics.ema_long:.2f} {fiat_currency}",
            f"🎢 {html.bold('ATR')} = ±{metrics.atr:.2f} {fiat_currency} (±{metrics.atr_percent}%)",
            f"📊 {html.bold('RSI')} = {html.italic(metrics.rsi_state.capitalize())} ({metrics.rsi:.2f})",
        ]
        ret = header + "\n".join(message_lines)
        return ret

    def format_persist_stop_loss_message(
        self, symbol: str, percent_value: float, limit_sell_order_guard_metrics_list: list[LimitSellOrderGuardMetrics]
    ) -> str:
        answer_text = (
            f"ℹ Stop loss for {html.bold(symbol)} at {html.bold(str(percent_value) + '%')} "
            + "has been successfully stored and it will be applied right now! \n\n"
            + html.bold(
                "⚠️ IMPORTANT NOTE: Limit Sell Order Guard Jobs has been DISABLED for PRECAUTION! "
                + "Please, enable it after double-check everything out!"
            )
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
                    + f"    * ⚖️ {html.bold('Break-even Price')} = {metrics.break_even_price} {fiat_currency}\n"
                    + f"    * 🚏 {html.bold('Stop Loss')} = {metrics.stop_loss_percent_value}%\n"
                    + f"    * 🛡️ {html.bold('Safeguard Stop Price = ' + str(metrics.safeguard_stop_price) + ' ' + fiat_currency)}"  # noqa: E501
                )
                answer_text += (
                    "\n  💡 "
                    + html.bold("HINTS (ATR Volatility-based)")
                    + " 💡\n"
                    + f"    * 🎢 {html.italic('Current ATR')} = ±{metrics.current_attr_value} {fiat_currency} (±{metrics.current_atr_percent}%)\n"  # noqa: E501
                    + f"    * 🚏 {html.bold('Suggested Stop Loss')} = {metrics.suggested_stop_loss_percent_value}%\n"  # noqa: E501
                    + f"    * 💰 {html.bold('Suggested Safeguard Stop Price')} = {metrics.suggested_safeguard_stop_price} {fiat_currency}\n"  # noqa: E501
                    + f"    * 🎯 {html.bold('Suggested Take Profit Price')} = {metrics.suggested_take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
                )
                if idx + 1 < len(limit_sell_order_guard_metrics_list):
                    answer_text += "\n\n"
        return answer_text

    def format_market_signals_message(self, symbol: str, market_signals: list[MarketSignalItem]) -> str:
        header = f"🚥 {html.bold('LAST MARKET SIGNALS')} for {html.bold(symbol)} 🚥\n\n"
        message_lines = []
        if not market_signals:
            message_lines.append(f"⚠️ No market signals found for {html.bold(symbol)}.")
        else:
            for signal in market_signals:
                *_, fiat_currency = symbol.split("/")
                formatted_timestamp = signal.timestamp.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d-%m-%Y %H:%M")
                timeframe = signal.timeframe.lower()
                signal_type = signal.signal_type.lower()
                rsi_state = signal.rsi_state.replace("_", " ").capitalize().strip()

                # Match background job alert style
                if timeframe == "4h":
                    if signal_type == "buy":
                        line = f"🚀🚀 - 🟢 - {html.bold('STRATEGIC BUY ALERT (4H)')}"
                    else:  # sell
                        line = f"⏬⏬ - 🔴 - {html.bold('STRATEGIC SELL ALERT (4H)')}"
                else:  # 1h
                    if signal_type == "buy":
                        line = f"🟢 - 🛒 {html.bold('BUY SIGNAL (1H)')}"
                    else:  # sell
                        line = f"🔴 - 🔚 {html.bold('SELL SIGNAL (1H)')}"
                # Append additional details
                line += (
                    f"\n  * 🕒 {html.code(formatted_timestamp)}"
                    f"\n  * 📊 RSI: {html.italic(rsi_state)}"
                    f"\n  * 🎢 ATR: ±{html.bold(f'{signal.atr:.2f} {fiat_currency} (±{signal.atr_percent}%)')}"
                    f"\n  * 💰 Closing Price: {html.code(f'{signal.closing_price:.2f} {fiat_currency}')}"
                    f"\n  * 📐 EMA Long: {html.code(f'{signal.ema_long_price:.2f} {fiat_currency}')}"
                )
                message_lines.append(line)
        ret = header + "\n\n".join(message_lines)
        return ret
