import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.services.vo.immediate_sell_order_item import ImmediateSellOrderItem

logger = logging.getLogger(__name__)


class LimitSellOrderGuardCacheService(metaclass=SingletonMeta):
    def __init__(self) -> None:
        # This will hold the IDs of orders to be immediately sold
        self._immediate_sell_orders_cache: dict[str, ImmediateSellOrderItem] = {}

    def mark_immediate_sell_order(self, immediate_sell_order: ImmediateSellOrderItem) -> None:
        """
        Marks a limit sell order to be immediately executed.
        This method updates the cache to reflect that the order should be processed immediately.
        """
        if immediate_sell_order.sell_order_id not in self._immediate_sell_orders_cache:
            self._immediate_sell_orders_cache[immediate_sell_order.sell_order_id] = immediate_sell_order
            logger.info(
                f"Order ID {immediate_sell_order.sell_order_id} "
                + f"has been marked for immediate sell of {immediate_sell_order.percent_to_sell} %."
            )
        else:
            logger.warning(f"Order ID {immediate_sell_order.sell_order_id} was already marked for immediate sell.")

    def pop_immediate_sell_order(self, sell_order_id: str) -> ImmediateSellOrderItem | None:
        """
        Checks if a limit sell order is marked for immediate execution.

        Args:
            sell_order_id (str): The ID of the limit sell order.

        Returns:
            ImmediateSellOrderItem | None:
        """
        ret = self._immediate_sell_orders_cache.pop(sell_order_id, None)
        return ret
