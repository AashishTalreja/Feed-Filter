"""
Provider-agnostic LLM client for the classification fallback.

Groq, Gemini and OpenAI all expose an OpenAI-compatible Chat Completions
API, so one client covers all of them: the provider only decides the
default base URL and model. Set LLM_PROVIDER + LLM_API_KEY in .env, and
optionally LLM_MODEL / LLM_BASE_URL to override the defaults (e.g. to
point at any other OpenAI-compatible server).

Kept separate from the LangGraph pipeline so the eval script can call
exactly the same prompt + parsing logic the API uses.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

PROVIDERS = {
    # Llama 4 Scout handles both text and images, so the vision fallback works.
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}

# Generous enough that "thinking" models (e.g. Gemini 2.5 Flash) don't spend
# the whole budget reasoning and return an empty answer.
MAX_TOKENS = 1024


@dataclass
class LLMResult:
    category: str
    confidence: float
    used_vision: bool


def is_configured() -> bool:
    return bool(settings.llm_api_key)


def _resolve() -> tuple[str, str]:
    defaults = PROVIDERS.get(settings.llm_provider.lower(), {})
    base_url = settings.llm_base_url or defaults.get("base_url")
    model = settings.llm_model or defaults.get("model")
    if not base_url or not model:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.llm_provider}': set LLM_BASE_URL "
            f"and LLM_MODEL, or use one of {sorted(PROVIDERS)}"
        )
    return base_url, model


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        base_url, _ = _resolve()
        _client = OpenAI(api_key=settings.llm_api_key, base_url=base_url, timeout=20.0, max_retries=1)
    return _client


def build_prompt(
    title: str,
    channel: str,
    description: str,
    categories: dict[str, str],
    examples: list[dict],
    with_image: bool,
) -> str:
    category_options = "\n".join(f"- {key}: {label}" for key, label in categories.items())
    examples_block = "\n".join(
        f'  - "{e["title"]}" -> {e["category"]}' for e in examples
    ) or "  (none)"
    vision_instruction = (
        "The video's thumbnail is attached. Use it as supporting evidence "
        "alongside the title and channel, not on its own: it often reveals "
        "the true content type when the title is ambiguous or clickbait "
        '(e.g. a video titled "X EXPLAINED" whose thumbnail clearly shows '
        "gameplay is Gaming, not Education).\n\n"
        if with_image else ""
    )
    return f"""You are classifying a YouTube video into exactly one official YouTube category.

{vision_instruction}Categories (key: label):
{category_options}

Similar previously-classified videos (for reference):
{examples_block}

Video to classify:
Title: {title}
Channel: {channel}
Description: {description}

Respond with a JSON object only: {{"category": "<category key from the list>", "confidence": <number between 0 and 1>}}"""


def _parse(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some models wrap JSON in prose or ```json fences despite JSON mode.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def classify(
    title: str,
    channel: str,
    description: str,
    categories: dict[str, str],
    examples: list[dict] | None = None,
    thumbnail: tuple[str, str] | None = None,
) -> LLMResult:
    """Classify one video. `categories` maps key -> label, `thumbnail` is
    (base64_data, media_type) from app.vision. Raises on API/parse errors;
    callers decide how to degrade. Returns a category key that is
    guaranteed to be in `categories`."""
    _, model = _resolve()
    with_image = thumbnail is not None
    prompt = build_prompt(title, channel, description, categories, examples or [], with_image)

    if with_image:
        b64_data, media_type = thumbnail
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64_data}"}},
        ]
    else:
        content = prompt

    request = dict(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    client = _get_client()
    try:
        response = client.chat.completions.create(**request, response_format={"type": "json_object"})
    except Exception as exc:  # noqa: BLE001
        # Not every model/provider combination supports JSON mode (some
        # reject it alongside images). Retry once without it; _parse copes.
        from openai import BadRequestError

        if not isinstance(exc, BadRequestError):
            raise
        logger.info("JSON mode rejected by %s, retrying without it: %s", model, exc)
        response = client.chat.completions.create(**request)

    parsed = _parse(response.choices[0].message.content)
    category = str(parsed.get("category", "")).strip()
    if category not in categories:
        raise ValueError(f"LLM returned a category outside the taxonomy: {category!r}")
    try:
        confidence = min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.5
    return LLMResult(category=category, confidence=confidence, used_vision=with_image)
