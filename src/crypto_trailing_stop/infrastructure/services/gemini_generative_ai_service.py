from collections.abc import AsyncIterator
from datetime import UTC, datetime
from os import path

from google import genai
from mako.template import Template

from crypto_trailing_stop.infrastructure.adapters.remote.gemini_remote_service import GeminiRemoteService


class GeminiGenerativeAiService:
    def __init__(self, gemini_remote_service: GeminiRemoteService):
        self._gemini_remote_service = gemini_remote_service
        self._generative_ai_market_analysis_prompt_template: Template | None = None
        self._prepare_mako_templates()

    async def get_generative_ai_market_analysis(
        self, symbol: str, formatted_metrics_list: list[str]
    ) -> AsyncIterator[genai.types.GenerateContentResponse]:
        now = datetime.now(UTC)
        rendered_prompt = self._generative_ai_market_analysis_prompt_template.render(
            symbol=symbol, formatted_date=now.strftime("%A, %d %B %Y"), formatted_metrics_list=formatted_metrics_list
        )
        response = await self._gemini_remote_service.generate_content_stream(prompts=rendered_prompt)
        return response

    def _prepare_mako_templates(self):
        generative_ai_market_analysis_prompt_file_path = path.realpath(
            path.join(path.dirname(__file__), "resources", "templates", "generative_ai_market_analysis_prompt.mako")
        )
        self._generative_ai_market_analysis_prompt_template = Template(  # nosec: B702
            filename=generative_ai_market_analysis_prompt_file_path
        )
