from faker import Faker

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from tests.helpers.object_mothers import Bit2MeTradeDtoObjectMother


def generate_trades(faker: Faker, opened_sell_bit2me_orders: list[Bit2MeOrderDto]) -> list[Bit2MeTradeDto]:
    buy_trades = []
    for sell_order in opened_sell_bit2me_orders:
        number_of_trades = faker.random_element([2, 4])
        for _ in range(number_of_trades):
            buy_trades.append(
                Bit2MeTradeDtoObjectMother.create(
                    side="buy",
                    symbol=sell_order.symbol,
                    price=sell_order.price * 0.5,
                    amount=sell_order.order_amount / number_of_trades,
                )
            )

    return buy_trades
