from asyncio import Lock

from crypto_trailing_stop.commons.constants import STOP_LOSS_STEPS_VALUE_LIST
from crypto_trailing_stop.infrastructure.database.models.risk_management import RiskManagement


class RiskManagementService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._default_risk_management_percent_value = STOP_LOSS_STEPS_VALUE_LIST[-1]

    async def get_risk_value(self) -> float:
        risk_management = await RiskManagement.objects().first()
        if risk_management:
            ret = risk_management.value
        else:
            ret = self._default_risk_management_percent_value
        return ret

    async def set_risk_value(self, value: float) -> None:
        # XXX: [JMSOLA] Disable Limit Sell Order Guard job for as a precaution,
        #      just in case we provoked expected situation!
        risk_management = await RiskManagement.objects().first()
        if risk_management:
            risk_management.value = value
        else:
            risk_management = RiskManagement({RiskManagement.value: value})
        await risk_management.save()
