import logging
from asyncio import Lock

import pydash

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.database.models.stop_loss_percent import StopLossPercent
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem

logger = logging.getLogger(__name__)


class StopLossPercentService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService, global_flag_service: GlobalFlagService) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = bit2me_remote_service
        self._global_flag_service = global_flag_service
        self._lock = Lock()

    async def find_all(self) -> list[StopLossPercentItem]:
        async with self._lock:
            stored_stop_loss_percent_list = await StopLossPercent.objects()
            ret = [
                StopLossPercentItem(symbol=current.symbol, value=current.value)
                for current in stored_stop_loss_percent_list
            ]
            additional_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies()
            for additional_crypto_currency in additional_crypto_currencies:
                if not any(current.symbol.lower() == additional_crypto_currency.lower() for current in ret):
                    ret.append(
                        StopLossPercentItem(
                            symbol=additional_crypto_currency.upper(),
                            value=self._configuration_properties.trailing_stop_loss_percent,
                        )
                    )
            ret = pydash.order_by(ret, ["symbol"])
            return ret

    async def find_symbol(self, symbol: str) -> StopLossPercentItem:
        async with self._lock:
            stop_loss_percent = await StopLossPercent.objects().where(StopLossPercent.symbol == symbol.upper()).first()
            if stop_loss_percent:
                ret = StopLossPercentItem(symbol=stop_loss_percent.symbol, value=stop_loss_percent.value)
            else:
                ret = StopLossPercentItem(
                    symbol=symbol.upper(), value=self._configuration_properties.trailing_stop_loss_percent
                )
            return ret

    async def save_or_update(
        self, item: StopLossPercentItem, *, force_disable_limit_sell_order_guard: bool = True
    ) -> None:
        async with self._lock:
            # XXX: [JMSOLA] Disable Limit Sell Order Guard job for as a precaution,
            #      just in case we provoked expected situation!
            if force_disable_limit_sell_order_guard:
                await self._global_flag_service.force_disable_by_name(name=GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)
            stop_loss_percent = await StopLossPercent.objects().where(StopLossPercent.symbol == item.symbol).first()
            if stop_loss_percent:
                stop_loss_percent.value = item.value
            else:
                stop_loss_percent = StopLossPercent(
                    {StopLossPercent.symbol: item.symbol, StopLossPercent.value: item.value}
                )
            await stop_loss_percent.save()
