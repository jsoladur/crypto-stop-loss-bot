from dependency_injector import containers, providers
from pyee.asyncio import AsyncIOEventEmitter

from crypto_trailing_stop.infrastructure.adapters.config.adapters_container import AdaptersContainer
from crypto_trailing_stop.infrastructure.services.config.services_container import ServicesContainer
from crypto_trailing_stop.infrastructure.tasks.config.tasks_container import TasksContainer


class InfrastructureContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    telegram_service = providers.Dependency()

    event_emitter = providers.Singleton(AsyncIOEventEmitter)

    adapters_container = providers.Container(AdaptersContainer, configuration_properties=configuration_properties)
    services_container = providers.Container(
        ServicesContainer,
        configuration_properties=configuration_properties,
        event_emitter=event_emitter,
        bit2me_remote_service=adapters_container.bit2me_remote_service,
        ccxt_remote_service=adapters_container.ccxt_remote_service,
        gemini_remote_service=adapters_container.gemini_remote_service,
        telegram_service=telegram_service,
    )
    tasks_container = providers.Container(
        TasksContainer,
        configuration_properties=configuration_properties,
        event_emitter=event_emitter,
        bit2me_remote_service=adapters_container.bit2me_remote_service,
        ccxt_remote_service=adapters_container.ccxt_remote_service,
        global_flag_service=services_container.global_flag_service,
        market_signal_service=services_container.market_signal_service,
        limit_sell_order_guard_cache_service=services_container.limit_sell_order_guard_cache_service,
        buy_sell_signals_config_service=services_container.buy_sell_signals_config_service,
        orders_analytics_service=services_container.orders_analytics_service,
        favourite_crypto_currency_service=services_container.favourite_crypto_currency_service,
        auto_buy_trader_config_service=services_container.auto_buy_trader_config_service,
        crypto_analytics_service=services_container.crypto_analytics_service,
        push_notification_service=services_container.push_notification_service,
        telegram_service=telegram_service,
    )
