from pydantic import BaseModel, Field


class Bit2MeTickersDto(BaseModel):
    timestamp: int
    symbol: str
    close: float | int | None = None
    bid: float | int | None = None
    ask: float | int | None = None
    open: float | int | None = None
    high: float | int | None = None
    low: float | int | None = None
    percentage: float | int | None = None
    base_volume: float | int | None = Field(None, alias="baseVolume")
    quote_volume: float | int | None = Field(None, alias="quoteVolume")

    @property
    def ask_or_close(self) -> float | int:
        """
        Returns the ask price if available, otherwise returns the close price.
        """
        if self.ask is None and self.close is None:  # pragma: no cover
            raise ValueError(f"{self.symbol} :: Both 'ask' and 'close' prices are None.")
        return self.ask if self.ask is not None else self.close

    @property
    def bid_or_close(self) -> float | int:
        """
        Returns the bid price if available, otherwise returns the close price.
        """
        if self.bid is None and self.close is None:  # pragma: no cover
            raise ValueError(f"{self.symbol} :: Both 'bid' and 'close' prices are None.")
        return self.bid if self.bid is not None else self.close
