from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _env_model() -> str:
    return os.getenv("GROQ_MODEL", _DEFAULT_GROQ_MODEL).strip() or _DEFAULT_GROQ_MODEL


def _env_base_url() -> str:
    return os.getenv("GROQ_BASE_URL", _DEFAULT_GROQ_BASE_URL).strip() or _DEFAULT_GROQ_BASE_URL


@dataclass
class ProviderConfig:
    """Groq/OpenAI-compat settings.

    Leave ``model`` and ``base_url`` empty to resolve from environment on each API call
    (after ``load_env()``), so edits to ``.env`` take effect without stale dataclass defaults.
    """

    provider: str = "groq"
    model: str = ""
    base_url: str = ""
    temperature: float = 0.0
    timeout: int = 45


class LLMProvider:
    def __init__(self, config: Optional[ProviderConfig] = None) -> None:
        self.config = config or ProviderConfig()

    def _resolved_model(self) -> str:
        explicit = self.config.model.strip()
        return explicit if explicit else _env_model()

    def _resolved_base_url(self) -> str:
        explicit = self.config.base_url.strip()
        return explicit if explicit else _env_base_url()

    def complete_json(self, prompt: str) -> dict[str, object]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is required for Groq provider calls.") from exc

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return {}

        base_url = self._resolved_base_url()
        model = self._resolved_model()

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self.config.timeout,
        )

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
            response_format={"type": "json_object"},
            max_tokens=700,
            seed=7,
        )
        content = completion.choices[0].message.content or "{}"
        return json.loads(content)

    def _system_prompt(self) -> str:
        prompt_path = Path(__file__).resolve().parent / "prompts" / "respond.md"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except OSError:
            return "Return JSON only with response and justification."
