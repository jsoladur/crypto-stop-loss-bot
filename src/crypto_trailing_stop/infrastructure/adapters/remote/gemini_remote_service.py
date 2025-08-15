import logging
from collections.abc import AsyncIterator

from google import genai

from crypto_trailing_stop.config import get_configuration_properties

logger = logging.getLogger(__name__)


class GeminiRemoteService:
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        if (
            self._configuration_properties.gemini_pro_api_enabled
            and not self._configuration_properties.gemini_pro_api_key
        ):
            raise ValueError("Gemini Pro API key is not configured!")

    async def generate_content_stream(
        self, prompts: str | list[str], *, model: str = "gemini-2.5-pro"
    ) -> AsyncIterator[genai.types.GenerateContentResponse]:
        client = genai.Client(api_key=self._configuration_properties.gemini_pro_api_key)
        response = await client.aio.models.generate_content_stream(model=model, contents=prompts)
        return response
