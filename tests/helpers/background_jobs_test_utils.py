from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService


async def disable_all_background_jobs_except(
    *, exclusion: GlobalFlagTypeEnum | list[GlobalFlagTypeEnum] | None = None
) -> None:
    # Pause job since won't be paused via start(..), stop(..)
    exclusion = exclusion or []
    exclusion = list(exclusion if isinstance(exclusion, (list, tuple, set, frozenset)) else [exclusion])
    # Always pause execution for Buy / Sell Signals
    if GlobalFlagTypeEnum.BUY_SELL_SIGNALS not in exclusion:
        task_manager = get_task_manager_instance()
        buy_sell_signals_task_service: BuySellSignalsTaskService = task_manager.get_tasks()[
            GlobalFlagTypeEnum.BUY_SELL_SIGNALS
        ]
        buy_sell_signals_task_service._job.pause()

    global_flag_service = GlobalFlagService()
    for flag in GlobalFlagTypeEnum:
        if not exclusion or flag not in exclusion:
            await global_flag_service.toggle_by_name(flag)
