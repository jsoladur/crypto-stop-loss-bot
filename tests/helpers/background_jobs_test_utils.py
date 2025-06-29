from crypto_trailing_stop.infrastructure.services import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum


async def disable_all_background_jobs_except(*, exclusion: GlobalFlagTypeEnum) -> None:
    global_flag_service = GlobalFlagService()
    for flag in GlobalFlagTypeEnum:
        if flag != exclusion:
            global_flag_service.toggle_by_name(flag)
