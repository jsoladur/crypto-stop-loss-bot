from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService


async def disable_all_background_jobs_except(*, exclusion: GlobalFlagTypeEnum | None = None) -> None:
    # Pause job since won't be paused via start(..), stop(..)
    if exclusion != GlobalFlagTypeEnum.BUY_SELL_SIGNALS:
        task_manager = get_task_manager_instance()
        buy_sell_signals_task_service: BuySellSignalsTaskService = task_manager.get_tasks()[
            GlobalFlagTypeEnum.BUY_SELL_SIGNALS
        ]
        buy_sell_signals_task_service._job.pause()
    # Always pause execution for Buy / Sell Signals
    global_flag_service = GlobalFlagService()
    for flag in GlobalFlagTypeEnum:
        if exclusion is None or flag != exclusion:
            await global_flag_service.toggle_by_name(flag)
