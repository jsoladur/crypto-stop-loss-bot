import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta

logger = logging.getLogger(__name__)


class LimitSellOrderGuardCacheService(metaclass=SingletonMeta):
    def __init__(self) -> None:
        # This will hold the IDs of orders to be immediately sold
        self._immediate_sell_orders_cache = set()

    def trigger_immediate_sell_limit_order(self, sell_order_id: str) -> None:
        """
        Marks a limit sell order to be immediately executed.
        This method updates the cache to reflect that the order should be processed immediately.
        """
        self._immediate_sell_orders_cache.add(sell_order_id)
        logger.info(f"Order ID {sell_order_id} has been marked for immediate sell.")

    def is_sell_order_marked_as_immediate_sell(self, sell_order_id: str) -> bool:
        """
        Checks if a given sell order ID is marked for immediate sell.
        """
        ret = sell_order_id in self._immediate_sell_orders_cache
        self._immediate_sell_orders_cache.discard(sell_order_id)
        return ret
