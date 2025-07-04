import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.database.decorators import transactional
from crypto_trailing_stop.infrastructure.database.models import GlobalFlag
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.global_flag_item import GlobalFlagItem

logger = logging.getLogger(__name__)


class GlobalFlagService(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._configuration_properties = get_configuration_properties()

    async def find_all(self) -> list[GlobalFlagItem]:
        flags = await GlobalFlag.objects()
        ret = []
        for current in GlobalFlagTypeEnum:
            persisted = next(filter(lambda n: GlobalFlagTypeEnum.from_value(n.name) == current, flags), None)
            ret.append(GlobalFlagItem(name=current, value=persisted is None or persisted.value is True))
        return ret

    @transactional
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

    @transactional
    async def force_disable_by_name(self, name: GlobalFlagTypeEnum) -> None:
        # Immediately stop the task!
        await self._toggle_task(name, value=False)
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = False
        else:
            global_flag = GlobalFlag(name=name.value, value=False)
        await global_flag.save()

    async def is_enabled_for(self, name: GlobalFlagTypeEnum) -> bool:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        return global_flag is None or global_flag.value is True

    async def _toggle_task(self, name: GlobalFlagTypeEnum, value: bool) -> None:
        # Communicate to task manager to start/stop the task
        from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance

        if value:
            await get_task_manager_instance().start(name)
        else:
            await get_task_manager_instance().stop(name)
