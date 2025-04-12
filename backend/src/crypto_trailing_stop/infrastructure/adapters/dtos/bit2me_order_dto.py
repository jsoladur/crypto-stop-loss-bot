from pydantic import BaseModel, ConfigDict
# {
# "id": "536ee1dc-528a-419e-9c00-5e04c010658d",
# "userId": "2bf436fc-43e6-459a-b647-6b446f72ad96",
# "side": "buy",
# "symbol": "B2M/EUR",
# "price": 65000.5,
# "orderAmount": 0.35,
# "filledAmount": 0,
# "dustAmount": 0,
# "status": "filled",
# "orderType": "limit",
# "cost": 22750.175,
# "createdAt": "2024-05-07T14:08:30.961Z",
# "updatedAt": "2024-05-07T14:08:45.647Z",
# "stopPrice": 0,
# "clientOrderId": null,
# "cancelReason": null,
# "postOnly": null,
# "timeInForce": "GTC",
# "feeAmount": 24.28260561,
# "feeCurrency": "B2M"
# }


class Bit2MeOrderDto(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, extra="ignore"
    )
    id: str
    side: str
    symbol: str
    price: float | int
