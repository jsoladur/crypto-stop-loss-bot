from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dependency_injector import containers, providers

from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from crypto_trailing_stop.infrastructure.tasks.global_flag_checker_task_service import GlobalFlagCheckerTaskService
from crypto_trailing_stop.infrastructure.tasks.limit_sell_order_guard_task_service import LimitSellOrderGuardTaskService
from crypto_trailing_stop.infrastructure.tasks.task_manager import TaskManager
from crypto_trailing_stop.infrastructure.tasks.trailing_stop_loss_task_service import TrailingStopLossTaskService


class TasksContainer(containers.DeclarativeContainer):
    __self__ = providers.Self()

    configuration_properties = providers.Dependency()
    event_emitter = providers.Dependency()

    ccxt_remote_service = providers.Dependency()

    operating_exchange_service = providers.Dependency()

    global_flag_service = providers.Dependency()
    market_signal_service = providers.Dependency()
    limit_sell_order_guard_cache_service = providers.Dependency()
    buy_sell_signals_config_service = providers.Dependency()
    orders_analytics_service = providers.Dependency()
    favourite_crypto_currency_service = providers.Dependency()
    auto_buy_trader_config_service = providers.Dependency()
    crypto_analytics_service = providers.Dependency()
    push_notification_service = providers.Dependency()
    telegram_service = providers.Dependency()

    scheduler = providers.Singleton(AsyncIOScheduler)

    buy_sell_signals_task_service = providers.Singleton(
        BuySellSignalsTaskService,
        configuration_properties=configuration_properties,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
        event_emitter=event_emitter,
        scheduler=scheduler,
        ccxt_remote_service=ccxt_remote_service,
        global_flag_service=global_flag_service,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        crypto_analytics_service=crypto_analytics_service,
        auto_buy_trader_config_service=auto_buy_trader_config_service,
    )

    limit_sell_order_guard_task_service = providers.Singleton(
        LimitSellOrderGuardTaskService,
        configuration_properties=configuration_properties,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
        scheduler=scheduler,
        market_signal_service=market_signal_service,
        ccxt_remote_service=ccxt_remote_service,
        limit_sell_order_guard_cache_service=limit_sell_order_guard_cache_service,
        favourite_crypto_currency_service=favourite_crypto_currency_service,
        buy_sell_signals_config_service=buy_sell_signals_config_service,
        crypto_analytics_service=crypto_analytics_service,
        orders_analytics_service=orders_analytics_service,
    )

    trailing_stop_loss_task_service = providers.Singleton(
        TrailingStopLossTaskService,
        configuration_properties=configuration_properties,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
        scheduler=scheduler,
        ccxt_remote_service=ccxt_remote_service,
        orders_analytics_service=orders_analytics_service,
    )

    global_flag_checker_task_service = providers.Singleton(
        GlobalFlagCheckerTaskService,
        configuration_properties=configuration_properties,
        operating_exchange_service=operating_exchange_service,
        push_notification_service=push_notification_service,
        telegram_service=telegram_service,
        scheduler=scheduler,
        global_flag_service=global_flag_service,
    )

    task_manager = providers.Singleton(TaskManager, global_flag_service=global_flag_service, tasks_container=__self__)
