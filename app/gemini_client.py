"""One door to the AI. Tries each configured provider in order (Gemini, OpenAI, router); the
first valid answer wins. Every reply is validated against a Pydantic schema; malformed JSON is
retried with a correction hint; temporary errors are retried with growing waits; permanent errors
(bad key, wrong model) move on to the next provider. There is no sample-data mode."""
import json
import logging
import time
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from .config import settings

log = logging.getLogger("ideonix.ai")
T = TypeVar("T", bound=BaseModel)
TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}


class GeminiError(RuntimeError):  # name kept so the rest of the code needs no changes
    pass


def _gemini_target(model: str):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key, http_options=types.HttpOptions(timeout=45_000))

    def call(system: str, user: str) -> str:
        r = client.models.generate_content(
            model=model, contents=system + "\n\n" + user,
            config=types.GenerateContentConfig(temperature=0.2), # type: ignore
        )
        return r.text or ""

    return call


def _openai_target(api_key: str, base_url: str, model: str, json_mode: bool):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=45)

    def call(system: str, user: str) -> str:
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        r=client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **extra) # type: ignore
        return r.choices[0].message.content

    return call


_targets = None


def get_targets():
    global _targets
    if _targets is None:
        t = []
        if settings.gemini_api_key and settings.gemini_model:
            t.append(("gemini", _gemini_target(settings.gemini_model)))
        if settings.gemini_api_key and settings.gemini_fallback_model:
            t.append(("gemini-backup", _gemini_target(settings.gemini_fallback_model)))
        if settings.openai_api_key and settings.openai_model:
            t.append(("openai", _openai_target(settings.openai_api_key, "", settings.openai_model, True)))
        if settings.router_api_key and settings.router_model:
            t.append(("router", _openai_target(settings.router_api_key, settings.router_base_url, settings.router_model, False)))
        _targets = t
    return _targets


def _clean(text: Optional[str]) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def generate_structured(prompt: str, schema: Type[T], *, retries: int = 3) -> T:
    targets = get_targets()
    if not targets:
        raise GeminiError("No AI provider is configured")
    system = (
        "You are a careful analyst. Reply with one JSON object only, no markdown, "
        "matching this JSON schema exactly:\n" + json.dumps(schema.model_json_schema())
    )
    errors = []
    for name, call in targets:
        repair = ""
        for attempt in range(retries + 1):
            try:
                text = _clean(call(system, prompt + repair))
                if not text:
                    raise ValueError("empty response")
                return schema.model_validate_json(text)
            except Exception as exc:
                msg = str(exc)[:200]
                code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                log.warning("%s attempt %d/%d failed: %s", name, attempt + 1, retries + 1, msg)
                errors.append(f"{name}: {msg}")
                if isinstance(exc, ValueError):
                    repair = f"\n\nYour previous reply was rejected: {msg}\nReturn only valid JSON matching the schema."
                elif isinstance(code, int) and code not in TRANSIENT_CODES:
                    break
                if attempt < retries:
                    time.sleep(min(2 ** (attempt + 1), 10))
    raise GeminiError("The AI service is unavailable right now. Details: " + " | ".join(errors[-2:]))