from typing import Literal

ReliableTimeframe = Literal["4h", "1h"]
Timeframe = Literal["4h", "1h", "30m"]
RSIState = Literal["neutral", "overbought", "oversold", "bullish_momentum"]
MarketSignalType = Literal["buy", "sell", "bearish_divergence", "bullish_divergence"]
