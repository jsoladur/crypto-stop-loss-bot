import logging
from typing import override

from aiogram import html

from crypto_trailing_stop.commons.constants import TRIGGER_BUY_ACTION_EVENT_NAME
from crypto_trailing_stop.commons.patterns import SingletonABCMeta
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.base import AbstractService
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem

logger = logging.getLogger(__name__)


class AutoEntryTraderEventHandlerService(AbstractService, metaclass=SingletonABCMeta):
    def __init__(self) -> None:
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._global_flag_service = GlobalFlagService()
        self._auto_buy_trader_config_service = AutoBuyTraderConfigService(
            bit2me_remote_service=self._bit2me_remote_service
        )

    @override
    def configure(self) -> None:
        event_emitter = get_event_emitter()
        event_emitter.add_listener(TRIGGER_BUY_ACTION_EVENT_NAME, self.on_buy_market_signal)

    async def on_buy_market_signal(self, market_signal_item: MarketSignalItem) -> None:
        try:
            is_enabled_for = await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_ENTRY_TRADER)
            if is_enabled_for:
                crypto_currency, *_ = market_signal_item.symbol.split("/")
                buy_trader_config = await self._auto_buy_trader_config_service.find_by_symbol(crypto_currency)
                if buy_trader_config.fiat_wallet_percent_assigned > 0:
                    # FIXME: To be implemented!
                    # Steps to achieve the creation of the BUY MARKET ORDER

                    # 1.) Call to GlobalSummaryService._calculate_current_value(..) to get the TOTAL EUR AMOUNT!
                    # 2.) Calculate the absolute value of EUR we can assign to this operation
                    # 3.) Check if ATR w is at least > 1% in order to create the BUY MARKET ORDER
                    # 4.) Call to await self._bit2me_remote_service.get_account_info(client=client) to get currency_code (EUR) # noqa: E501
                    # 5.) Call to https://gateway.bit2me.com/v1/trading/wallet/balance for getting Bit2ME EUR Wallet balance # noqa: E501
                    # 6.) Calculate how much we are getting from previous point in EUR in order to create BUY order
                    # 7.) Get the current tickers.close price for calculate the order_amount
                    # 8.) Create the BUY MARKET ORDER
                    # 9.) Wait for betting BUY MARKET ORDER filled
                    # 10.) Create Limit Sell Order
                    #      - limit_price = tickers.close * suggested_take_profit_atr_multiplier
                    # 11) Calculate metrics
                    # 12.) Calc to StopLossPercentService to save_or_update(..) stop loss
                    # since we are going to get a suggested one.
                    raise NotImplementedError("To be implemented")
        except Exception as e:
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    async def _notify_alert(self, market_signal_item: MarketSignalItem, body_message: str) -> None:
        telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
            notification_type=PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT
        )
        if telegram_chat_ids:
            tickers: Bit2MeTickersDto = await self._bit2me_remote_service.get_tickers_by_symbol(
                market_signal_item.symbol
            )
            crypto_currency, fiat_currency = tickers.symbol.split("/")
            message = f"✅✅ {html.bold('MARKET BUY ORDER CREATED')} ✅✅\n\n"
            message += f"{body_message}\n"
            message += html.bold(f"🔥 {crypto_currency} current price is {tickers.close} {fiat_currency}")
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)
