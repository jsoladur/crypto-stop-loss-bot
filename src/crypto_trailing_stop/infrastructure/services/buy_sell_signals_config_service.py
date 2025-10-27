import logging

import pydash

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.database.models.buy_sell_signals_config import BuySellSignalsConfig
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem

logger = logging.getLogger(__name__)


class BuySellSignalsConfigService:
    def __init__(
        self,
        configuration_properties: ConfigurationProperties,
        favourite_crypto_currency_service: FavouriteCryptoCurrencyService,
    ) -> None:
        self._configuration_properties = configuration_properties
        self._favourite_crypto_currency_service = favourite_crypto_currency_service

    async def find_all(self) -> list[BuySellSignalsConfigItem]:
        stored_config_list = await BuySellSignalsConfig.objects()
        ret = [self._convert_to_value_object(current) for current in stored_config_list]
        additional_crypto_currencies = await self._favourite_crypto_currency_service.find_all()
        for additional_crypto_currency in additional_crypto_currencies:
            if not any(current.symbol.lower() == additional_crypto_currency.lower() for current in ret):
                ret.append(self._get_defaults_by_symbol(symbol=additional_crypto_currency))
        ret = pydash.order_by(ret, ["symbol"])
        return ret

    async def find_by_symbols(self, symbols: list[str]) -> list[BuySellSignalsConfigItem]:
        symbols = [symbol.upper() for symbol in symbols]
        stored_config_list = await BuySellSignalsConfig.objects().where(
            BuySellSignalsConfig.symbol.is_in(list(symbols))
        )
        ret = [self._convert_to_value_object(current) for current in stored_config_list]
        for symbol in symbols:
            if not any(current.symbol.upper() == symbol.upper() for current in ret):
                ret.append(self._get_defaults_by_symbol(symbol=symbol))
        ret = pydash.order_by(ret, ["symbol"])
        return ret

    async def find_by_symbol(self, symbol: str) -> BuySellSignalsConfigItem:
        config = await BuySellSignalsConfig.objects().where(BuySellSignalsConfig.symbol == symbol.upper()).first()
        if config:
            ret = self._convert_to_value_object(config)
        else:
            ret = self._get_defaults_by_symbol(symbol=symbol)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Using {repr(ret)} for {symbol}...")
        return ret

    async def toggle_enable_exit_on_take_profit_by_symbol(self, symbol: str) -> BuySellSignalsConfigItem:
        item = await self.find_by_symbol(symbol)
        item.enable_exit_on_take_profit = not item.enable_exit_on_take_profit
        await self.save_or_update(item)
        logger.info(f"Auto Exit ATR Take Profit for {symbol} has been set to {item.enable_exit_on_take_profit}")
        return item

    async def save_or_update(self, item: BuySellSignalsConfigItem) -> None:
        # XXX: [JMSOLA] Disable Limit Sell Order Guard job for as a precaution,
        #      just in case we provoked expected situation!
        config = await BuySellSignalsConfig.objects().where(BuySellSignalsConfig.symbol == item.symbol).first()
        if config:
            config.ema_short_value = item.ema_short_value
            config.ema_mid_value = item.ema_mid_value
            config.ema_long_value = item.ema_long_value
            config.stop_loss_atr_multiplier = item.stop_loss_atr_multiplier
            config.take_profit_atr_multiplier = item.take_profit_atr_multiplier
            config.enable_adx_filter = item.enable_adx_filter
            config.adx_threshold = item.adx_threshold
            config.enable_buy_volume_filter = item.enable_buy_volume_filter
            config.buy_min_volume_threshold = item.buy_min_volume_threshold
            config.buy_max_volume_threshold = item.buy_max_volume_threshold
            config.enable_sell_volume_filter = item.enable_sell_volume_filter
            config.sell_min_volume_threshold = item.sell_min_volume_threshold
            config.enable_exit_on_sell_signal = item.enable_exit_on_sell_signal
            config.enable_exit_on_divergence_signal = item.enable_exit_on_divergence_signal
            config.enable_exit_on_take_profit = item.enable_exit_on_take_profit
        else:
            config = BuySellSignalsConfig(
                {
                    BuySellSignalsConfig.symbol: item.symbol,
                    BuySellSignalsConfig.ema_short_value: item.ema_short_value,
                    BuySellSignalsConfig.ema_mid_value: item.ema_mid_value,
                    BuySellSignalsConfig.ema_long_value: item.ema_long_value,
                    BuySellSignalsConfig.stop_loss_atr_multiplier: item.stop_loss_atr_multiplier,
                    BuySellSignalsConfig.take_profit_atr_multiplier: item.take_profit_atr_multiplier,
                    BuySellSignalsConfig.enable_adx_filter: item.enable_adx_filter,
                    BuySellSignalsConfig.adx_threshold: item.adx_threshold,
                    BuySellSignalsConfig.enable_buy_volume_filter: item.enable_buy_volume_filter,
                    BuySellSignalsConfig.buy_min_volume_threshold: item.buy_min_volume_threshold,
                    BuySellSignalsConfig.buy_max_volume_threshold: item.buy_max_volume_threshold,
                    BuySellSignalsConfig.enable_sell_volume_filter: item.enable_sell_volume_filter,
                    BuySellSignalsConfig.sell_min_volume_threshold: item.sell_min_volume_threshold,
                    BuySellSignalsConfig.enable_exit_on_sell_signal: item.enable_exit_on_sell_signal,
                    BuySellSignalsConfig.enable_exit_on_divergence_signal: item.enable_exit_on_divergence_signal,
                    BuySellSignalsConfig.enable_exit_on_take_profit: item.enable_exit_on_take_profit,
                }
            )
        await config.save()

    def _convert_to_value_object(self, buy_sell_signals_config: BuySellSignalsConfig) -> BuySellSignalsConfigItem:
        return BuySellSignalsConfigItem(
            symbol=buy_sell_signals_config.symbol,
            ema_short_value=buy_sell_signals_config.ema_short_value,
            ema_mid_value=buy_sell_signals_config.ema_mid_value,
            ema_long_value=buy_sell_signals_config.ema_long_value,
            stop_loss_atr_multiplier=buy_sell_signals_config.stop_loss_atr_multiplier,
            take_profit_atr_multiplier=buy_sell_signals_config.take_profit_atr_multiplier,
            enable_adx_filter=buy_sell_signals_config.enable_adx_filter,
            adx_threshold=buy_sell_signals_config.adx_threshold,
            enable_buy_volume_filter=buy_sell_signals_config.enable_buy_volume_filter,
            buy_min_volume_threshold=buy_sell_signals_config.buy_min_volume_threshold,
            buy_max_volume_threshold=buy_sell_signals_config.buy_max_volume_threshold,
            enable_sell_volume_filter=buy_sell_signals_config.enable_sell_volume_filter,
            sell_min_volume_threshold=buy_sell_signals_config.sell_min_volume_threshold,
            enable_exit_on_sell_signal=buy_sell_signals_config.enable_exit_on_sell_signal,
            enable_exit_on_divergence_signal=buy_sell_signals_config.enable_exit_on_divergence_signal,
            enable_exit_on_take_profit=buy_sell_signals_config.enable_exit_on_take_profit,
        )

    def _get_defaults_by_symbol(self, symbol: str) -> BuySellSignalsConfigItem:
        return BuySellSignalsConfigItem(
            symbol=symbol.upper(),
            ema_short_value=self._configuration_properties.buy_sell_signals_ema_short_value,
            ema_mid_value=self._configuration_properties.buy_sell_signals_ema_mid_value,
            ema_long_value=self._configuration_properties.buy_sell_signals_ema_long_value,
            stop_loss_atr_multiplier=self._configuration_properties.suggested_stop_loss_atr_multiplier,
            take_profit_atr_multiplier=self._configuration_properties.suggested_take_profit_atr_multiplier,
            adx_threshold=self._configuration_properties.buy_sell_signals_adx_threshold,
            buy_min_volume_threshold=self._configuration_properties.buy_sell_signals_min_volume_threshold,
            buy_max_volume_threshold=self._configuration_properties.buy_sell_signals_max_volume_threshold,
            sell_min_volume_threshold=self._configuration_properties.buy_sell_signals_min_volume_threshold,
        )
