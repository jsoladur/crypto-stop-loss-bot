import logging

import cachebox
import pydash

from crypto_trailing_stop.commons.constants import DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS
from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.database.models.auto_buy_trader_config import AutoBuyTraderConfig
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem

logger = logging.getLogger(__name__)


class AutoBuyTraderConfigService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = bit2me_remote_service

    async def find_all(self) -> list[AutoBuyTraderConfigItem]:
        stored_config_list = await AutoBuyTraderConfig.objects()
        ret = [
            AutoBuyTraderConfigItem(
                symbol=current.symbol, fiat_wallet_percent_assigned=current.fiat_wallet_percent_assigned
            )
            for current in stored_config_list
        ]
        additional_crypto_currencies = await self._get_additional_crypto_currencies()
        for additional_crypto_currency in additional_crypto_currencies:
            if not any(current.symbol.lower() == additional_crypto_currency.lower() for current in ret):
                ret.append(AutoBuyTraderConfigItem(symbol=additional_crypto_currency.upper()))
        ret = pydash.order_by(ret, ["symbol"])
        return ret

    async def find_by_symbol(self, symbol: str) -> AutoBuyTraderConfigItem:
        config = await AutoBuyTraderConfig.objects().where(AutoBuyTraderConfig.symbol == symbol.upper()).first()
        if config:
            ret = AutoBuyTraderConfigItem(
                symbol=config.symbol, fiat_wallet_percent_assigned=config.fiat_wallet_percent_assigned
            )
        else:
            ret = AutoBuyTraderConfigItem(symbol=symbol.upper())
        return ret

    async def save_or_update(self, item: AutoBuyTraderConfigItem) -> None:
        # XXX: [JMSOLA] Disable Limit Sell Order Guard job for as a precaution,
        #      just in case we provoked expected situation!
        config = await AutoBuyTraderConfig.objects().where(AutoBuyTraderConfig.symbol == item.symbol).first()
        if config:
            config.fiat_wallet_percent_assigned = item.fiat_wallet_percent_assigned
        else:
            config = AutoBuyTraderConfig(
                {
                    AutoBuyTraderConfig.symbol: item.symbol,
                    AutoBuyTraderConfig.fiat_wallet_percent_assigned: item.fiat_wallet_percent_assigned,
                }
            )
        await config.save()

    @cachebox.cachedmethod(cachebox.TTLCache(0, ttl=DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS))
    async def _get_additional_crypto_currencies(self) -> list[str]:
        return await self._bit2me_remote_service.get_favourite_crypto_currencies()
