from dependency_injector import containers, providers

from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.auto_entry_trader_event_handler_service import (
    AutoEntryTraderEventHandlerService,
)
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.gemini_generative_ai_service import GeminiGenerativeAiService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from crypto_trailing_stop.infrastructure.services.limit_sell_order_guard_cache_service import (
    LimitSellOrderGuardCacheService,
)
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService


class ServicesContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    event_emitter = providers.Dependency()
    telegram_service = providers.Dependency()

    ccxt_remote_service = providers.Dependency()
    gemini_remote_service = providers.Dependency()

    operating_exchange_service = providers.Dependency()

    global_flag_service = providers.Singleton(GlobalFlagService, configuration_properties=configuration_properties)

    push_notification_service = providers.Singleton(
        PushNotificationService, configuration_properties=configuration_properties
    )

    favourite_crypto_currency_service = providers.Singleton(
        FavouriteCryptoCurrencyService, operating_exchange_service=operating_exchange_service
    )

    buy_sell_signals_config_service = providers.Singleton(
        BuySellSignalsConfigService,
        configuration_properties=configuration_properties,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
    )

    stop_loss_percent_service = providers.Singleton(
        StopLossPercentService,
        configuration_properties=configuration_properties,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        global_flag_service=global_flag_service,
    )

    global_summary_service = providers.Singleton(
        GlobalSummaryService, operating_exchange_service=operating_exchange_service
    )

    auto_buy_trader_config_service = providers.Singleton(
        AutoBuyTraderConfigService,
        configuration_properties=configuration_properties,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
    )

    crypto_analytics_service = providers.Singleton(
        CryptoAnalyticsService,
        operating_exchange_service=operating_exchange_service,
        ccxt_remote_service=ccxt_remote_service,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
    )

    orders_analytics_service = providers.Singleton(
        OrdersAnalyticsService,
        operating_exchange_service=operating_exchange_service,
        ccxt_remote_service=ccxt_remote_service,
        stop_loss_percent_service=stop_loss_percent_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
        crypto_analytics_service=crypto_analytics_service,
    )

    auto_entry_trader_event_handler_service = providers.Singleton(
        AutoEntryTraderEventHandlerService,
        configuration_properties=configuration_properties,
        event_emitter=event_emitter,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
        ccxt_remote_service=ccxt_remote_service,
        global_flag_service=global_flag_service,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
        auto_buy_trader_config_service=auto_buy_trader_config_service,
        stop_loss_percent_service=stop_loss_percent_service,
        global_summary_service=global_summary_service,
        crypto_analytics_service=crypto_analytics_service,
        orders_analytics_service=orders_analytics_service,
    )

    gemini_generative_ai_service = providers.Singleton(
        GeminiGenerativeAiService, gemini_remote_service=gemini_remote_service
    )

    limit_sell_order_guard_cache_service = providers.Singleton(LimitSellOrderGuardCacheService)

    market_signal_service = providers.Singleton(
        MarketSignalService,
        configuration_properties=configuration_properties,
        event_emitter=event_emitter,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
    )
