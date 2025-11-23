import logging
from typing import TYPE_CHECKING

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.database.models.global_flag import GlobalFlag
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.global_flag_item import GlobalFlagItem

if TYPE_CHECKING:
    from crypto_trailing_stop.infrastructure.tasks.task_manager import TaskManager

logger = logging.getLogger(__name__)


class GlobalFlagService:
    def __init__(self, configuration_properties: ConfigurationProperties) -> None:
        self._configuration_properties = configuration_properties
        self._task_manager = None

    def set_task_manager(self, task_manager: "TaskManager") -> None:
        self._task_manager = task_manager

    async def find_all(self) -> list[GlobalFlagItem]:
        flags = await GlobalFlag.objects()
        ret = []
        for current in GlobalFlagTypeEnum:
            persisted = next(filter(lambda n: GlobalFlagTypeEnum.from_value(n.name) == current, flags), None)
            ret.append(GlobalFlagItem(name=current, value=persisted is None or persisted.value is True))
        return ret

    async def toggle_by_name(self, name: GlobalFlagTypeEnum) -> GlobalFlagItem:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = not global_flag.value
        else:
            global_flag = GlobalFlag(name=name.value, value=False)
        await self._toggle_task(name, value=global_flag.value)
        await global_flag.save()
        ret = GlobalFlagItem(name=GlobalFlagTypeEnum.from_value(global_flag.name), value=global_flag.value)
        return ret

    async def force_disable_by_name(self, name: GlobalFlagTypeEnum) -> None:
        # Immediately stop the task!
        await self._toggle_task(name, value=False)
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = False
        else:
            global_flag = GlobalFlag(name=name.value, value=False)
        await global_flag.save()

    async def force_enable_by_name(self, name: GlobalFlagTypeEnum) -> None:
        # Immediately stop the task!
        await self._toggle_task(name, value=True)
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = True
        else:
            global_flag = GlobalFlag(name=name.value, value=True)
        await global_flag.save()

    async def is_enabled_for(self, name: GlobalFlagTypeEnum) -> bool:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        return global_flag is None or global_flag.value is True

    async def _toggle_task(self, name: GlobalFlagTypeEnum, value: bool) -> None:
        if value:
            await self._task_manager.start(name)
        else:
            await self._task_manager.stop(name)
