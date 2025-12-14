import logging
from typing import List

from src.application.ports import LLMPort
from src.infrastructure.config import Settings


logger = logging.getLogger(__name__)


class MistralLLMAdapter(LLMPort):
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._client = None
        self._model = self.settings.mistral_model
        self._init_client()

    def _init_client(self):
        api_key = self.settings.mistral_api_key
        if not api_key:
            logger.error("Mistral API key is missing.")
            self._client = None
            return
        try:
            from mistralai import Mistral
            self._client = Mistral(api_key=api_key)
        except Exception as e:
            logger.exception("Failed to initialize Mistral client: %s", e)
            self._client = None

    def generate_intake_assessment_json(self, messages: List[dict]) -> str:
        if not self._client:
            raise RuntimeError("Mistral client not initialized (missing API key or import error)")
        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
            )
            # Return the assistant content
            content = response.choices[0].message.content
            return content
        except Exception as e:
            logger.exception("Mistral chat call failed: %s", e)
            raise
