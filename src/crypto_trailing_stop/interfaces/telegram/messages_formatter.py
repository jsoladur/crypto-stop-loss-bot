from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pydash
from aiogram import html

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.account_info import AccountInfo
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_tickers import SymbolTickers
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.trading_wallet_balance import (
    TradingWalletBalance,
)
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.global_summary import GlobalSummary
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.services.vo.trade_now_hints import LeveragedPositionHints, TradeNowHints


class MessagesFormatter:
    def format_global_summary(self, global_summary: GlobalSummary) -> str:
        message_lines = [
            "=============================",
            "📊 GLOBAL SUMMARY 📊",
            "=============================",
            f"🏦 DEPOSITS: {global_summary.total_deposits:.2f}€",
            f"🏧 WITHDRAWALS: {global_summary.withdrawls:.2f}€",
            "----------------------------------------------------",
            f"💸 TOTAL INVESTED: {global_summary.total_invested:.2f}€",
            f"💰 CURRENT: {global_summary.current_value:.2f}€",
            "----------------------------------------------------",
            f"🤑 NET REVENUE: {(global_summary.net_revenue):.2f} EUR",
            "=============================",
        ]
        message = "\n".join(message_lines)
        return message

    def format_trading_wallet_balances(
        self,
        account_info: AccountInfo,
        trading_wallet_balances: list[TradingWalletBalance],
        total_portfolio_fiat_amount: float,
    ) -> str:
        # Filter no effective wallet balances
        trading_wallet_balances = pydash.order_by(
            [
                trading_wallet_balance
                for trading_wallet_balance in trading_wallet_balances
                if trading_wallet_balance.is_effective
                or trading_wallet_balance.currency.lower() == account_info.currency_code.lower()
            ],
            "currency",
        )
        message_lines = ["===========================", "🪙 SPOT BALANCES 🪙", "==========================="]
        if trading_wallet_balances:
            for wallet_balance in trading_wallet_balances:
                balance = round(wallet_balance.balance, ndigits=4)
                blocked_balance = round(wallet_balance.blocked_balance, ndigits=4)
                total_balance = round(wallet_balance.total_balance, ndigits=4)
                message_lines.append(
                    f"🏷️ {html.bold(wallet_balance.currency)} \n"
                    f"   💰 Available: {html.code(balance)}\n"
                    f"   🔒 Blocked: {html.code(blocked_balance)}\n"
                    f"   ➕ {html.bold('TOTAL')}: {html.code(total_balance)}"
                )
        else:
            message_lines.append("✳️ No trading wallet balances found.")
        message_lines.append(
            html.italic(
                f"📊  {html.bold('Total Portfolio')}: {total_portfolio_fiat_amount} {account_info.currency_code}"  # noqa: E501
            )
        )
        fiat_currency_wallet_balance = next(
            filter(lambda twb: twb.currency.lower() == account_info.currency_code.lower(), trading_wallet_balances),
            None,
        )
        if fiat_currency_wallet_balance and total_portfolio_fiat_amount > 0:
            no_invested_percent = round(
                (fiat_currency_wallet_balance.balance / total_portfolio_fiat_amount) * 100, ndigits=2
            )
            invested_percent_value = round(100 - no_invested_percent, ndigits=2)
            message_lines.extend(
                [
                    html.italic(f"💸 {html.bold('Invested')}: {invested_percent_value}%"),
                    html.italic(f"💤 {html.bold('To invest')}: {no_invested_percent}%"),
                ]
            )
        ret = "\n".join(message_lines)
        return ret

    def format_current_prices_message(self, tickers_list: SymbolTickers) -> str:
        message_lines = ["===========================", "💵 CURRENT PRICES 💵", "==========================="]
        for tickers in tickers_list:
            crypto_currency, fiat_currency = tickers.symbol.split("/")
            message_lines.append(
                f"🔥 {html.bold(crypto_currency.upper())} 💰 {html.bold(str(tickers.close) + ' ' + fiat_currency)}"
            )
        ret = "\n".join(message_lines)
        return ret

    def format_current_crypto_metrics_message(
        self, over_candlestick: CandleStickEnum, tickers: SymbolTickers, metrics: CryptoMarketMetrics
    ) -> str:
        *_, fiat_currency = metrics.symbol.split("/")
        message_lines = [
            f"🧮 {html.bold(over_candlestick.name.upper() + ' METRICS')} for {html.bold(metrics.symbol)} 🧮",
            "==============================",
            f"📅 {html.bold('Timestamp')} = {self._format_timestamp_with_timezone(metrics.timestamp + timedelta(hours=1))}",  # noqa: E501
            "----------------------------------------------------",
            f"🔥 {html.bold('CURRENT PRICE')} = {html.code(str(tickers.close) + ' ' + fiat_currency)}",
            "----------------------------------------------------",
            f"💰 {html.bold('Closing Price')} = {html.code(f'{metrics.closing_price} {fiat_currency}')}",
            f"🚪 {html.bold('Opening Price')} = {html.code(f'{metrics.opening_price} {fiat_currency}')}",
            f"🔺 {html.bold('Highest Price')} = {html.code(f'{metrics.highest_price} {fiat_currency}')}",
            f"🔻 {html.bold('Lowest Price')} = {html.code(f'{metrics.lowest_price} {fiat_currency}')}",
            f"📈 {html.bold('EMA Short')} = {html.code(f'{metrics.ema_short} {fiat_currency}')}",
            f"📉 {html.bold('EMA Mid')} = {html.code(f'{metrics.ema_mid} {fiat_currency}')}",
            f"📐 {html.bold('EMA Long')} = {html.code(f'{metrics.ema_long} {fiat_currency}')}",
            f"💹 {html.bold('MACD Line')} = {self._get_macd_icon(metrics.macd_line)} {metrics.macd_line}",
            f"🧨 {html.bold('MACD Signal')} = {self._get_macd_icon(metrics.macd_signal)} {metrics.macd_signal} ",
            f"♊ {html.bold('MACD Hist')} = {self._get_macd_icon(metrics.macd_hist)} {metrics.macd_hist}",
            f"💈 {html.bold('Bollinger Bands')}",
            f"  ↓ {html.bold('BB Upper')} = 🔽 {metrics.bb_upper} {fiat_currency}",
            f"  - {html.bold('BB Middle')} = ➖ {metrics.bb_middle} {fiat_currency}",
            f"  ↑ {html.bold('BB Lower')} = 🔼 {metrics.bb_lower} {fiat_currency}",
            f"🎢 {html.bold('ATR')} = ±{metrics.atr} {fiat_currency} (±{metrics.atr_percent}%)",
            f"📊 {html.bold('RSI')} = {html.italic(pydash.start_case(metrics.rsi_state))} ({metrics.rsi})",
            f"🔊 {html.bold('Relative Vol.')} = {self._get_relative_vol_icon(metrics.relative_vol)} {metrics.relative_vol}x (Avg)",  # noqa: E501
            f"📶 {html.bold('ADX')} = {self._get_adx_icon(metrics)} {metrics.adx}",
            f"  ➕{html.bold('DI')} = {metrics.adx_pos}",
            f"  ➖{html.bold('DI')} = {metrics.adx_neg}",
            "----------------------------------------------------",
            f"🐻 {html.bold('Bearish Divergence')} = {'💀 YES' if metrics.bearish_divergence else '🌤️ No'}",
            f"🚀 {html.bold('Bullish Divergence')} = {'🟢 YES' if metrics.bullish_divergence else '🧘 No'}",
            "==============================",
        ]
        ret = "\n".join(message_lines)
        return ret

    def format_buy_sell_signals_config_message(self, item: BuySellSignalsConfigItem) -> str:
        return (
            f"📈 EMA Short = {html.code(item.ema_short_value)}\n"
            f"📉 EMA Mid = {html.code(item.ema_mid_value)}\n"
            f"📐 EMA Long = {html.code(item.ema_long_value)}\n"
            f"🛡️ SL ATR x = {html.code(item.stop_loss_atr_multiplier)}\n"
            f"🏁 TP ATR x = {html.code(item.take_profit_atr_multiplier)}\n"
            f"📶 ADX Filter enabled? = {'🟢' if item.enable_adx_filter else '🟥'}\n"
            f"🔦 ADX Threshold = {html.code(item.adx_threshold) if item.enable_adx_filter else html.italic('(n/a)')}\n"
            f"🚩 BUY Volume Filter enabled? = {'🟢' if item.enable_buy_volume_filter else '🟥'}\n"
            f"🔊 BUY Min Volume Threshold = {html.code(item.buy_min_volume_threshold) if item.enable_buy_volume_filter else html.italic('(n/a)')}\n"  # noqa: E501
            f"🔇 BUY Max Volume Threshold = {html.code(item.buy_max_volume_threshold) if item.enable_buy_volume_filter else html.italic('(n/a)')}\n"  # noqa: E501
            f"💣 SELL Volume Filter enabled? = {'🟢' if item.enable_sell_volume_filter else '🟥'}\n"
            f"🔊 SELL Min Volume Threshold = {html.code(item.sell_min_volume_threshold) if item.enable_sell_volume_filter else html.italic('(n/a)')}\n"  # noqa: E501
            f"🚨 Exit on SELL Signal enabled? = {'🟢' if item.enable_exit_on_sell_signal else '🟥'}\n"
            f"💀 Exit on BEARISH Divergence enabled? = {'🟢' if item.enable_exit_on_divergence_signal else '🟥'}\n"
            f"🎯 Exit on Take Profit enabled? = {'🟢' if item.enable_exit_on_take_profit else '🟥'}\n\n"
        )

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
        answer_text += f"\n\n{self._format_limit_sell_order_guard_metrics_list(limit_sell_order_guard_metrics_list)}"
        return answer_text

    def format_limit_sell_order_guard_metrics(self, metrics: LimitSellOrderGuardMetrics) -> str:
        crypto_currency, fiat_currency = metrics.sell_order.symbol.split("/")
        answer_text = (
            f"🚀 {html.bold(metrics.sell_order.order_type.upper() + ' Sell Order')} :: "
            + f"💰 {metrics.sell_order.amount} {crypto_currency}, "  # noqa: E501
            + f"further sell at {html.bold(str(metrics.sell_order.price) + ' ' + fiat_currency)}"
        )
        if metrics.sell_order.order_type == "stop-limit":
            answer_text += (
                " (when price reaches stop limit price at"
                + f" {html.bold(str(metrics.sell_order.stop_price) + ' ' + fiat_currency)})"
            )
        answer_text += (
            "\n"
            + f"   🔥 {html.bold(crypto_currency.upper() + ' (Bid) Price')} = {metrics.current_price} {fiat_currency}\n"
            + f"   🤑 {html.bold('Current Profit')} = {metrics.current_profit} {fiat_currency}\n"
            + f"   🏦 {html.bold('Net Revenue')} = {metrics.net_revenue} {fiat_currency}\n"
            + "   ---------------------------------------------------- \n"
            + f"   💳 {html.bold('Buy Price')} = {metrics.avg_buy_price} {fiat_currency}\n"
            + f"   🧊 {html.bold('Break-even Price')} = {metrics.break_even_price} {fiat_currency}\n"
            + "   ---------------------------------------------------- \n"
            + f"   🚏 {html.bold('Stop Loss')} = {metrics.stop_loss_percent_value}%\n"
            + f"   🛡️ {html.bold('Stop Price = ' + str(metrics.safeguard_stop_price) + ' ' + fiat_currency)}\n"  # noqa: E501
            + f"   🏆 {html.bold('Take Profit')} = {metrics.take_profit_percent_value}%\n"  # noqa: E501
            + f"   🎯 {html.bold('Take Profit Price')} = {metrics.take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
            + "  ---------------------------------------------------- \n"
            + f"   ⚖️ {html.bold('Profit Factor (R:R)')} = {html.code(metrics.profit_factor)}\n"
            + f"   🟢 {html.bold('Potential Profit at TP')} = {html.code(str(metrics.potential_profit_at_tp) + ' ' + fiat_currency)}\n"  # noqa: E501
            + f"   🔴 {html.bold('Potential Loss at SL')} = {html.code('-' + str(metrics.potential_loss_at_sl) + ' ' + fiat_currency)}"  # noqa: E501
        )
        answer_text += (
            "\n  ---------------------------------------------------- \n"
            f"  💡 {html.italic('HINTS (ATR Volatility-based)')} 💡\n"
            + "  ---------------------------------------------------- \n"
            + f"   🎢 {html.italic('ATR')} = ±{metrics.current_attr_value} {fiat_currency} (±{metrics.current_atr_percent}%)\n"  # noqa: E501
            + f"   🚏 {html.bold('ATR Stop Loss')} = {metrics.suggested_stop_loss_percent_value}%\n"  # noqa: E501
            + f"   💰 {html.bold('ATR Safeguard Stop Price')} = {metrics.suggested_safeguard_stop_price} {fiat_currency}\n"  # noqa: E501
            + f"   🏆 {html.bold('ATR Take Profit')} = {metrics.suggested_take_profit_percent_value}%\n"  # noqa: E501
            + f"   🎯 {html.bold('ATR Take Profit Price')} = {metrics.suggested_take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
            + "  ---------------------------------------------------- "
        )
        return answer_text

    def format_market_signals_message(
        self, symbol: str, trading_market_config: SymbolMarketConfig, market_signals: list[MarketSignalItem]
    ) -> str:
        header = f"🚥 {html.bold('LAST MARKET SIGNALS')} for {html.bold(symbol)} 🚥\n\n"
        message_lines = []
        if not market_signals:
            message_lines.append(f"⚠️ No market signals found for {html.bold(symbol)}.")
        else:
            for signal in market_signals:
                *_, fiat_currency = symbol.split("/")
                formatted_timestamp = self._format_timestamp_with_timezone(signal.timestamp)
                timeframe = signal.timeframe.lower()
                signal_type = signal.signal_type.lower()
                rsi_state = pydash.start_case(signal.rsi_state)

                # Match background job alert style
                if signal.is_divergence_signal:
                    if signal_type == "bearish_divergence":
                        line = "💀💀 - ⚠️ - "
                    else:
                        line = "🚀🚀 - 🟢 - "
                    line += f"{html.bold(pydash.start_case(signal_type).upper()) + ' (' + timeframe.upper() + ')'}"
                elif timeframe == "4h":
                    if signal_type == "buy":
                        line = f"⏬⏬ - ⚠️ - {html.bold('UPTREND EXHAUSTION ALERT (4H)')}"
                    else:  # sell
                        line = f"🚀🚀 - 🟢 - {html.bold('DOWNTREND EXHAUSTION ALERT (4H)')}"
                else:  # 1h
                    if signal_type == "buy":
                        line = f"🟢 - 🛒 {html.bold('BUY SIGNAL (1H)')}"
                    else:  # sell
                        line = f"🔴 - 🔚 {html.bold('SELL SIGNAL (1H)')}"
                # Append additional details
                formatted_atr = round(signal.atr, ndigits=trading_market_config.price_precision)
                formatted_closing_price = round(signal.closing_price, ndigits=trading_market_config.price_precision)
                formatted_ema_long_price = round(signal.ema_long_price, ndigits=trading_market_config.price_precision)
                line += (
                    f"\n  * 🕒 {html.code(formatted_timestamp)}"
                    f"\n  * 📊 RSI: {html.italic(rsi_state)}"
                    f"\n  * 🎢 ATR: ±{html.bold(f'{formatted_atr} {fiat_currency} (±{signal.get_atr_percent(trading_market_config)}%)')}"  # noqa: E501
                    f"\n  * 💰 Closing Price: {html.code(f'{formatted_closing_price} {fiat_currency}')}"
                    f"\n  * 📐 EMA Long: {html.code(f'{formatted_ema_long_price} {fiat_currency}')}"
                )
                message_lines.append(line)
        ret = header + "\n\n".join(message_lines)
        return ret

    def format_trade_now_hints(self, hints: TradeNowHints) -> str:
        tickers = hints.tickers
        metrics = hints.crypto_market_metrics
        *_, fiat_currency = hints.symbol.split("/")
        header = f"🔀 {html.bold('TRADE NOW CALCULATOR')} :: {html.bold(hints.symbol)} 🔀"
        market_status_lines = [
            "\n" + html.bold("📊 Current Market Status:"),
            f"   🔥 {html.italic('Current Price')} = {html.code(f'{tickers.close:.4f} {fiat_currency}')}",
            f"  🎢 {html.italic('ATR')} = ±{html.code(f'{metrics.atr:.4f} {fiat_currency}')} (±{metrics.atr_percent:.2f}%)",  # noqa: E501
        ]
        params_lines = [
            "\n" + html.bold("⚙️ Technical Parameters (ATR-based):"),
            f"   🚏 {html.bold('ATR Stop Loss')} = {hints.stop_loss_percent_value}%",
            f"   🏆 {html.bold('ATR Take Profit')} = {hints.take_profit_percent_value}%",
            f"   ⚖️ {html.bold('Profit Factor')} = {html.bold(hints.profit_factor)}",
        ]
        risk_data = hints.long
        risk_lines = [
            "\n" + html.bold("💰 Capital & Risk (@ " + str(hints.leverage_value) + "x Leverage):"),
            f"   💵 {html.bold('Capital as Margin')} = {html.code(f'{risk_data.required_margin:.2f} {fiat_currency}')} ({hints.fiat_wallet_percent_assigned}%)",  # noqa: E501
            f"   📦 {html.bold('Total Position Size')} = {html.code(f'{risk_data.position_size:.2f} {fiat_currency}')}",  # noqa: E501
            f"   💼 {html.italic('Risk from Total Capital')} = {html.bold(f'{risk_data.risk_as_percent_of_total_capital:.2f}%')}",  # noqa: E501
            f"   🟢 {html.italic('Profit if TP is triggered')} = {html.code(f'{risk_data.profit_at_stop_loss:.2f} {fiat_currency}')}",  # noqa: E501
            f"   🔴 {html.italic('Losses if SL is triggered')} = {html.code(f'-{risk_data.loss_at_stop_loss:.2f} {fiat_currency}')}",  # noqa: E501
        ]
        long_lines = self._format_position_hints(hints.long, fiat_currency)
        short_lines = self._format_position_hints(hints.short, fiat_currency)
        message = "\n".join([header] + market_status_lines + params_lines + risk_lines + long_lines + short_lines)
        return message

    def _format_position_hints(self, pos: LeveragedPositionHints, fiat_currency) -> list[str]:
        if pos.position_type == "Long":
            icon = "🟢"
            title = "LONG Position"
            entry_price_label = "Entry (Ask)"
        else:
            icon = "🔴"
            title = "SHORT Position"
            entry_price_label = "Entry (Bid)"
        lines = [
            f"\n{icon} If you open a new {html.bold(title)}:",
            f"   ▶️ {html.bold(entry_price_label)} ={html.code(f'{pos.entry_price:.4f} {fiat_currency}')}",
            f"   💰 {html.bold('ATR Safeguard Stop Price')} = {html.code(f'{pos.stop_loss_price:.4f} {fiat_currency}')}",  # noqa: E501
            f"   🎯 {html.bold('ATR Take Profit Price')} = {html.code(f'{pos.take_profit_price:.4f} {fiat_currency}')}",
        ]
        if pos.is_safe_from_liquidation:
            lines.append(f"   ✅ {html.italic('Safety: SL is before Liquidation Price.')}")
        else:
            lines.append(
                f"   🚨 {html.bold('DANGER: LIQUIDATION')}\n"
                f"    {html.italic('Your SL is BEYOND your Liquidation Price of')} {html.code(f'~{pos.liquidation_price:.4f} {fiat_currency}')}."  # noqa: E501
                f" {html.bold('Your position will be liquidated BEFORE the SL is hit.')}"
            )
        return lines

    def _format_limit_sell_order_guard_metrics_list(
        self, limit_sell_order_guard_metrics_list: list[LimitSellOrderGuardMetrics]
    ) -> str:
        if limit_sell_order_guard_metrics_list:
            answer_text = f"📤📤 {html.bold('SELL Orders')} 📤📤\n\n"
            for idx, metrics in enumerate(limit_sell_order_guard_metrics_list):
                answer_text += f"- {self.format_limit_sell_order_guard_metrics(metrics)}"
                if idx + 1 < len(limit_sell_order_guard_metrics_list):
                    answer_text += "\n"
        else:
            answer_text = "✳️ There are no currently opened SELL orders."
        return answer_text

    def _format_timestamp_with_timezone(self, timestamp: datetime, *, zoneinfo: str = "Europe/Madrid") -> str:
        return timestamp.astimezone(ZoneInfo(zoneinfo)).strftime("%d-%m-%Y %H:%M")

    def _get_macd_icon(self, macd_value: float | int) -> str:
        if macd_value > 0:
            # Upward momentum
            macd_hist_icon = "🟢"
        elif macd_value < 0:
            # Downward momentum
            macd_hist_icon = "🔻"
        else:
            # Neutral / crossover point
            macd_hist_icon = "🟰"
        return macd_hist_icon

    def _get_relative_vol_icon(self, relative_vol: float) -> str:
        if relative_vol > 1:
            # High relative volume
            relative_vol_icon = "🟢"
        elif relative_vol < 1:
            # Low relative volume
            relative_vol_icon = "🔻"
        else:
            # Neutral relative volume
            relative_vol_icon = "🟰"
        return relative_vol_icon

    def _get_adx_icon(self, metrics: CryptoMarketMetrics) -> str:
        if metrics.adx_pos > metrics.adx_neg:
            # Positive strenght
            adx_icon = "🟢"
        elif metrics.adx_neg > metrics.adx_pos:
            # Negative strenght
            adx_icon = "🔻"
        else:
            # Neutral strenght (consolidation momentum)
            adx_icon = "🟰"
        return adx_icon
