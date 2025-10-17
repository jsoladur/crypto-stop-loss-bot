import logging

import pydash

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.database.models.auto_buy_trader_config import AutoBuyTraderConfig
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem

logger = logging.getLogger(__name__)


class AutoBuyTraderConfigService:
    def __init__(
        self,
        configuration_properties: ConfigurationProperties,
        favourite_crypto_currency_service: FavouriteCryptoCurrencyService,
    ) -> None:
        self._configuration_properties = configuration_properties
        self._favourite_crypto_currency_service = favourite_crypto_currency_service

    async def find_all(
        self, *, include_favourite_cryptos: bool = True, order_by_symbol: bool = True
    ) -> list[AutoBuyTraderConfigItem]:
        stored_config_list = await AutoBuyTraderConfig.objects()
        ret = [
            AutoBuyTraderConfigItem(
                symbol=current.symbol, fiat_wallet_percent_assigned=current.fiat_wallet_percent_assigned
            )
            for current in stored_config_list
        ]
        if include_favourite_cryptos:
            additional_crypto_currencies = await self._favourite_crypto_currency_service.find_all()
            for additional_crypto_currency in additional_crypto_currencies:
                if not any(current.symbol.lower() == additional_crypto_currency.lower() for current in ret):
                    ret.append(AutoBuyTraderConfigItem(symbol=additional_crypto_currency.upper()))
        if order_by_symbol:
            # Sort by symbol
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
