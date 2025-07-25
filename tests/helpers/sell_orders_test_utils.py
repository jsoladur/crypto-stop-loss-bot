from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from tests.helpers.object_mothers import Bit2MeTradeDtoObjectMother


def generate_trades(
    faker: Faker, opened_sell_bit2me_orders: list[Bit2MeOrderDto], *, number_of_trades: int | None = None
) -> tuple[list[Bit2MeTradeDto], list[tuple[Bit2MeOrderDto, float]]]:
    buy_trades: list[Bit2MeTradeDto] = []
    buy_prices: list[tuple[Bit2MeOrderDto, float]] = []
    for sell_order in opened_sell_bit2me_orders:
        numerator, denominator = 0.0, 0.0
        number_of_trades = number_of_trades or faker.random_element([2, 4])
        for _ in range(number_of_trades):
            current_buy_trade = Bit2MeTradeDtoObjectMother.create(
                side="buy",
                symbol=sell_order.symbol,
                price=sell_order.price * 0.5,
                amount=sell_order.order_amount / number_of_trades,
            )
            buy_trades.append(current_buy_trade)
            numerator += current_buy_trade.price * current_buy_trade.amount
            denominator += current_buy_trade.amount
        buy_prices.append((sell_order, round(numerator / denominator, ndigits=2)))

    return buy_trades, buy_prices
