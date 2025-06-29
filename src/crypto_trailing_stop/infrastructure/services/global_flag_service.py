import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
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

    async def toggle_by_name(self, name: GlobalFlagTypeEnum) -> GlobalFlagItem:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = not global_flag.value
        else:
            global_flag = GlobalFlag(name=name.value, value=False)
        await global_flag.save()
        ret = GlobalFlagItem(name=GlobalFlagTypeEnum.from_value(global_flag.name), value=global_flag.value)
        return ret

    async def force_disable_by_name(self, name: GlobalFlagTypeEnum) -> None:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        if global_flag:
            global_flag.value = False
        else:
            global_flag = GlobalFlag(name=name.value, value=False)
        await global_flag.save()

    async def is_enabled_for(self, name: GlobalFlagTypeEnum) -> bool:
        global_flag = await GlobalFlag.objects().where(GlobalFlag.name == name.value).first()
        return global_flag is None or global_flag.value is True
