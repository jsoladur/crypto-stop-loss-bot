from aiogram import html

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem


class MessagesFormatter(metaclass=SingletonMeta):
    def format_market_signals_message(self, symbol: str, market_signals: list[MarketSignalItem]) -> str:
        header = f"🚥 {html.bold('LAST MARKET SIGNALS')} for {html.bold(symbol)} 🚥\n\n"
        message_lines = []
        if not market_signals:
            message_lines.append(f"⚠️ No market signals found for {html.bold(symbol)}.")
        else:
            for signal in market_signals:
                formatted_timestamp = signal.timestamp.strftime("%d-%m-%Y %H:%M")
                timeframe = signal.timeframe.lower()
                signal_type = signal.signal_type.lower()

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

                # Append timestamp (always same for all cases)
                line += f"\n🕒 {html.code(formatted_timestamp)}"
                message_lines.append(line)
        ret = header + "\n\n".join(message_lines)
        return ret
