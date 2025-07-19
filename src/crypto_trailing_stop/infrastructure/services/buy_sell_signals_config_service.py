import logging

import cachebox
import pydash

from crypto_trailing_stop.commons.constants import DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS
from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.database.models.buy_sell_signals_config import BuySellSignalsConfig
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem

logger = logging.getLogger(__name__)


class BuySellSignalsConfigService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = bit2me_remote_service

    async def find_all(self) -> list[BuySellSignalsConfigItem]:
        stored_config_list = await BuySellSignalsConfig.objects()
        ret = [
            BuySellSignalsConfigItem(
                symbol=current.symbol,
                ema_short_value=current.ema_short_value,
                ema_mid_value=current.ema_mid_value,
                ema_long_value=current.ema_long_value,
                stop_loss_atr_multiplier=current.stop_loss_atr_multiplier,
                take_profit_atr_multiplier=current.take_profit_atr_multiplier,
                auto_exit_sell_1h=current.auto_exit_sell_1h,
                auto_exit_atr_take_profit=current.auto_exit_atr_take_profit,
            )
            for current in stored_config_list
        ]
        additional_crypto_currencies = await self._get_additional_crypto_currencies()
        for additional_crypto_currency in additional_crypto_currencies:
            if not any(current.symbol.lower() == additional_crypto_currency.lower() for current in ret):
                ret.append(BuySellSignalsConfigItem(symbol=additional_crypto_currency.upper()))
        ret = pydash.order_by(ret, ["symbol"])
        return ret

    async def find_by_symbol(self, symbol: str) -> BuySellSignalsConfigItem:
        config = await BuySellSignalsConfig.objects().where(BuySellSignalsConfig.symbol == symbol.upper()).first()
        if config:
            ret = BuySellSignalsConfigItem(
                symbol=config.symbol,
                ema_short_value=config.ema_short_value,
                ema_mid_value=config.ema_mid_value,
                ema_long_value=config.ema_long_value,
                stop_loss_atr_multiplier=config.stop_loss_atr_multiplier,
                take_profit_atr_multiplier=config.take_profit_atr_multiplier,
                auto_exit_sell_1h=config.auto_exit_sell_1h,
                auto_exit_atr_take_profit=config.auto_exit_atr_take_profit,
            )
        else:
            ret = BuySellSignalsConfigItem(symbol=symbol.upper())
        logger.info(f"Using {repr(ret)} for {symbol}...")
        return ret

    async def save_or_update(self, item: BuySellSignalsConfigItem) -> None:
        # XXX: [JMSOLA] Disable Limit Sell Order Guard job for as a precaution,
        #      just in case we provoked expected situation!
        config = await BuySellSignalsConfig.objects().where(BuySellSignalsConfig.symbol == item.symbol).first()
        if config:
            config.ema_short_value = item.ema_short_value
            config.ema_mid_value = item.ema_mid_value
            config.ema_long_value = item.ema_long_value
            config.auto_exit_sell_1h = item.auto_exit_sell_1h
            config.auto_exit_atr_take_profit = item.auto_exit_atr_take_profit
            config.stop_loss_atr_multiplier = (item.stop_loss_atr_multiplier,)
            config.take_profit_atr_multiplier = (item.take_profit_atr_multiplier,)
        else:
            config = BuySellSignalsConfig(
                {
                    BuySellSignalsConfig.symbol: item.symbol,
                    BuySellSignalsConfig.ema_short_value: item.ema_short_value,
                    BuySellSignalsConfig.ema_mid_value: item.ema_mid_value,
                    BuySellSignalsConfig.ema_long_value: item.ema_long_value,
                    BuySellSignalsConfig.auto_exit_sell_1h: item.auto_exit_sell_1h,
                    BuySellSignalsConfig.auto_exit_atr_take_profit: item.auto_exit_atr_take_profit,
                    BuySellSignalsConfig.stop_loss_atr_multiplier: item.stop_loss_atr_multiplier,
                    BuySellSignalsConfig.take_profit_atr_multiplier: item.take_profit_atr_multiplier,
                }
            )
        await config.save()

    @cachebox.cachedmethod(cachebox.TTLCache(0, ttl=DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS))
    async def _get_additional_crypto_currencies(self) -> list[str]:
        return await self._bit2me_remote_service.get_favourite_crypto_currencies()
