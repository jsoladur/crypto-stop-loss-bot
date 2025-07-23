from zoneinfo import ZoneInfo

import pydash
from aiogram import html

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem


class MessagesFormatter(metaclass=SingletonMeta):
    def format_trading_wallet_balances(
        self, account_info: Bit2MeAccountInfoDto, trading_wallet_balances: list[Bit2MeTradingWalletBalanceDto]
    ) -> str:
        # Filter no effective wallet balances
        trading_wallet_balances = pydash.order_by(
            [
                trading_wallet_balance
                for trading_wallet_balance in trading_wallet_balances
                if trading_wallet_balance.is_effective
                or trading_wallet_balance.currency.lower() == account_info.profile.currency_code.lower()
            ],
            "currency",
        )
        message_lines = ["===========================", "🪙 PRO WALLET BALANCES 🪙", "==========================="]
        for idx, wallet_balance in enumerate(trading_wallet_balances):
            balance = round(wallet_balance.balance, ndigits=4)
            blocked_balance = round(wallet_balance.blocked_balance, ndigits=4)
            total_balance = round(wallet_balance.total_balance, ndigits=4)
            message_lines.append(
                f"🏷️ {html.bold(wallet_balance.currency)} \n"
                f"   💰 Available: {html.code(balance)}\n"
                f"   🔒 Blocked: {html.code(blocked_balance)}\n"
                f"   ➕ {html.bold('TOTAL')}: {html.code(total_balance)}"
            )
        ret = "\n".join(message_lines)
        return ret

    def format_current_prices_message(self, tickers_list: Bit2MeTickersDto) -> str:
        message_lines = ["===========================", "💵 CURRENT PRICES 💵", "==========================="]
        for tickers in tickers_list:
            crypto_currency, fiat_currency = tickers.symbol.split("/")
            message_lines.append(
                f"🔥 {html.bold(crypto_currency.upper())} 💰 {html.bold(str(tickers.close) + ' ' + fiat_currency)}"
            )
        ret = "\n".join(message_lines)
        return ret

    def format_current_crypto_metrics_message(self, metrics: CryptoMarketMetrics) -> str:
        *_, fiat_currency = metrics.symbol.split("/")
        if metrics.macd_hist > 0:
            macd_hist_icon = "🟢"  # Upward momentum
        elif metrics.macd_hist < 0:
            macd_hist_icon = "🔻"  # Downward momentum
        else:
            macd_hist_icon = "🟰"  # Neutral / crossover point
        header = f"🧮 {html.bold('CURRENT METRICS')} for {html.bold(metrics.symbol)} 🧮\n\n"
        message_lines = [
            f"💰 {html.bold('Current Price')} = {html.code(f'{metrics.closing_price} {fiat_currency}')}",
            f"📈 {html.bold('EMA Short')} = {metrics.ema_short} {fiat_currency}",
            f"📉 {html.bold('EMA Mid')} = {metrics.ema_mid} {fiat_currency}",
            f"📐 {html.bold('EMA Long')} = {metrics.ema_long} {fiat_currency}",
            f"♊ {html.bold('MACD Hist')} = {macd_hist_icon} {metrics.macd_hist}",
            f"🎢 {html.bold('ATR')} = ±{metrics.atr} {fiat_currency} (±{metrics.atr_percent}%)",
            f"📊 {html.bold('RSI')} = {html.italic(pydash.start_case(metrics.rsi_state))} ({metrics.rsi})",
            f"📶 {html.bold('ADX')} = {metrics.adx}",
            f"  ➕{html.bold('DI')} = {metrics.adx_pos}",
            f"  ➖{html.bold('DI')} = {metrics.adx_neg}",
        ]
        ret = header + "\n".join(message_lines)
        return ret

    def format_buy_sell_signals_config_message(self, item: BuySellSignalsConfigItem) -> str:
        buy_sell_signals_config_formatted = (
            f"📈 EMA Short Value = {html.code(item.ema_short_value)}\n"
            + f"📉 EMA Mid Value = {html.code(item.ema_mid_value)}\n"
            + f"📐 EMA Long Value = {html.code(item.ema_long_value)}\n"
            + f"🛡️ Stop Loss ATR Factor = {html.code(item.stop_loss_atr_multiplier)}\n"
            + f"🏁 Take Profit ATR Factor = {html.code(item.take_profit_atr_multiplier)}\n"
            + f"📶 Filter Noise using ADX? = {'🟢' if item.filter_noise_using_adx else '🟥'}\n"
            + f"🚨 Auto-Exit SELL 1h enabled? = {'🟢' if item.auto_exit_sell_1h else '🟥'}\n"
            + f"🎯 Auto-Exit Take Profit enabled? = {'🟢' if item.auto_exit_atr_take_profit else '🟥'}\n\n"
        )

        return buy_sell_signals_config_formatted

    def format_persist_stop_loss_message(
        self, symbol: str, percent_value: float, limit_sell_order_guard_metrics_list: list[LimitSellOrderGuardMetrics]
    ) -> str:
        answer_text = (
            f"ℹ️ Stop loss for {html.bold(symbol)} at {html.bold(str(percent_value) + '%')} "
            + "has been successfully stored and it will be applied right now! \n\n"
            + html.bold(
                "⚠️ IMPORTANT NOTE: Limit Sell Order Guard Jobs has been DISABLED for PRECAUTION! "
                + "Please, enable it after double-check everything out!"
            )
        )
        answer_text += f"\n\n{self.format_limit_sell_order_guard_metrics(limit_sell_order_guard_metrics_list)}"
        return answer_text

    def format_limit_sell_order_guard_metrics(
        self, limit_sell_order_guard_metrics_list: list[LimitSellOrderGuardMetrics]
    ) -> str:
        if limit_sell_order_guard_metrics_list:
            answer_text = f"📤📤 {html.bold('SELL Orders')} 📤📤\n\n"
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
        else:
            answer_text = "✳️ There are no currently opened SELL orders."
        return answer_text

    def format_market_signals_message(self, symbol: str, market_signals: list[MarketSignalItem]) -> str:
        ndigits = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE)
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
                rsi_state = pydash.start_case(signal.rsi_state)

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
                formatted_atr = round(signal.atr, ndigits=ndigits)
                formatted_closing_price = round(signal.closing_price, ndigits=ndigits)
                formatted_ema_long_price = round(signal.ema_long_price, ndigits=ndigits)
                line += (
                    f"\n  * 🕒 {html.code(formatted_timestamp)}"
                    f"\n  * 📊 RSI: {html.italic(rsi_state)}"
                    f"\n  * 🎢 ATR: ±{html.bold(f'{formatted_atr} {fiat_currency} (±{signal.atr_percent}%)')}"
                    f"\n  * 💰 Closing Price: {html.code(f'{formatted_closing_price} {fiat_currency}')}"
                    f"\n  * 📐 EMA Long: {html.code(f'{formatted_ema_long_price} {fiat_currency}')}"
                )
                message_lines.append(line)
        ret = header + "\n\n".join(message_lines)
        return ret
