from pydantic import BaseModel, ConfigDict, Field


class LoginDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    tg_user_id: str = Field(..., alias="tgUserId")
    tg_chat_id: str = Field(..., alias="tgChatId")
    tg_bot_id: str = Field(..., alias="tgBotId")
