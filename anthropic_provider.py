#!/usr/bin/env python3
"""
AnthropicProvider - Claude API implementation for hcaptcha-challenger.

Drop-in replacement for GeminiProvider. Implements ChatProvider Protocol
so hcaptcha-challenger can use Claude (via Anthropic API or OpenRouter/Claudibe)
to solve hCaptcha image challenges.

Usage:
    from anthropic_provider import AnthropicProvider
    provider = AnthropicProvider(api_key="sk-...", model="claude-sonnet-4-20250514")
    # Pass to AgentV or Reasoner as `provider=`
"""
import asyncio
import base64
import json
import re
from pathlib import Path
from typing import List, Type, TypeVar, cast

import httpx
from loguru import logger
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed

ResponseT = TypeVar("ResponseT", bound=BaseModel)


def extract_first_json_block(text: str) -> dict | None:
    """Extract the first JSON code block from text."""
    pattern = r"```json\s*([\s\S]*?)```"
    matches = re.findall(pattern, text)
    if matches:
        return json.loads(matches[0])
    # Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _image_to_base64(path: Path) -> tuple[str, str]:
    """Read image file and return (base64_data, media_type)."""
    suffix = path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


def _schema_to_description(schema: Type[BaseModel]) -> str:
    """Convert pydantic schema to a JSON description for the prompt."""
    s = schema.model_json_schema()
    props = s.get("properties", {})
    lines = []
    for name, info in props.items():
        typ = info.get("type", "string")
        desc = info.get("description", "")
        lines.append(f'  "{name}": ({typ}) {desc}')
    return "{\n" + ",\n".join(lines) + "\n}"


class AnthropicProvider:
    """
    Anthropic Claude-based chat provider implementation.
    Implements the ChatProvider protocol from hcaptcha-challenger.

    Supports:
    - Direct Anthropic API (api.anthropic.com)
    - OpenRouter (openrouter.ai) — set base_url
    - Any OpenAI-compatible proxy that forwards to Claude
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._last_response = None

    @property
    def last_response(self):
        return self._last_response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry request ({retry_state.attempt_number}/3) - "
            f"Wait 3s - Exception: {retry_state.outcome.exception()}"
        ),
    )
    async def generate_with_images(
        self,
        *,
        images: List[Path],
        response_schema: Type[ResponseT],
        user_prompt: str | None = None,
        description: str | None = None,
        **kwargs,
    ) -> ResponseT:
        """
        Generate content with image inputs using Claude API.

        Args:
            images: List of image file paths.
            response_schema: Pydantic model for structured output.
            user_prompt: User prompt text.
            description: System instruction.
        Returns:
            Parsed response matching response_schema.
        """
        # Build content blocks
        content_blocks = []

        # Add images as base64
        valid_files = [f for f in images if f and Path(f).exists()]
        for img_path in valid_files:
            b64_data, media_type = _image_to_base64(Path(img_path))
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data,
                },
            })

        # Add user prompt with schema guidance
        schema_desc = _schema_to_description(response_schema)
        prompt_parts = []
        if user_prompt:
            prompt_parts.append(user_prompt)
        prompt_parts.append(
            f"\nRespond with ONLY valid JSON matching this schema:\n{schema_desc}\n"
            "No markdown code blocks, no extra text. Just the JSON object."
        )
        content_blocks.append({"type": "text", "text": "\n".join(prompt_parts)})

        # Build request
        messages = [{"role": "user", "content": content_blocks}]

        body = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": messages,
        }
        if description:
            body["system"] = description

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # If using OpenRouter, adjust headers
        if "openrouter" in self._base_url:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            }

        url = f"{self._base_url}/v1/messages"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        self._last_response = data

        # Extract text from response
        response_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                response_text += block.get("text", "")

        # Parse JSON response
        # Try direct parse first
        try:
            parsed = json.loads(response_text)
            return response_schema(**parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Try extracting from code block
        json_data = extract_first_json_block(response_text)
        if json_data:
            return response_schema(**json_data)

        raise ValueError(f"Failed to parse Claude response: {response_text[:500]}")

    def cache_response(self, path: Path) -> None:
        """Cache the last response."""
        if not self._last_response:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._last_response, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")
