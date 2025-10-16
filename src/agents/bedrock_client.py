"""Thin wrapper around the AWS Bedrock runtime for hackathon demos."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError


class BedrockInvocationError(RuntimeError):
    """Raised when the Bedrock runtime fails to respond."""


class BedrockClient:
    """Simple helper for invoking Bedrock models."""

    def __init__(self, *, region_name: Optional[str] = None) -> None:
        self.region_name = region_name or os.getenv("BEDROCK_REGION") or "us-east-1"
        self._client = boto3.client("bedrock-runtime", region_name=self.region_name)

    def invoke(self, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self._client.invoke_model(  # type: ignore[attr-defined]
                modelId=model_id,
                body=json.dumps(payload).encode("utf-8"),
                accept="application/json",
                contentType="application/json",
            )
        except (NoCredentialsError, ClientError, BotoCoreError) as exc:  # pragma: no cover - passthrough to fallback
            raise BedrockInvocationError(str(exc)) from exc

        body = response.get("body")
        if hasattr(body, "read"):
            data = body.read().decode("utf-8")
        else:
            data = body
        return json.loads(data)


# --- Helpers -----------------------------------------------------------------

def _build_payload(model_id: str, prompt: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
    """Craft a provider-specific payload for Bedrock models."""

    if model_id.startswith("anthropic."):
        return {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    if model_id.startswith("mistral."):
        return {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }

    if model_id.startswith("meta."):
        return {
            "prompt": prompt,
            "max_gen_len": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }

    return {
        "inputText": prompt,
        "textGenerationConfig": {"temperature": temperature, "maxTokenCount": max_tokens},
    }


def _extract_text(model_id: str, response: Dict[str, Any]) -> Optional[str]:
    """Normalize provider responses into a plain text string."""

    output = response.get("output")
    if isinstance(output, dict) and isinstance(output.get("text"), str):
        return output["text"]

    if model_id.startswith("anthropic."):
        pieces = []
        for block in response.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                pieces.append(block.get("text", ""))
        return "".join(pieces) or None

    outputs = response.get("outputs")
    if isinstance(outputs, list) and outputs:
        first = outputs[0]
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return first["text"]

    if isinstance(response.get("generation"), str):
        return response["generation"]

    if isinstance(response.get("response"), str):
        return response["response"]

    return None


def _extract_usage(response: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Map Bedrock usage metadata into a consistent shape when present."""

    usage = response.get("usage")
    if isinstance(usage, dict):
        mapped = {
            "inputTokens": usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("promptTokenCount"),
            "outputTokens": usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("generatedTokenCount"),
        }
        return {k: v for k, v in mapped.items() if isinstance(v, int)}

    prompt_tokens = response.get("prompt_token_count")
    completion_tokens = response.get("generation_token_count") or response.get(
        "completion_token_count"
    )
    if isinstance(prompt_tokens, int) or isinstance(completion_tokens, int):
        mapped = {
            "inputTokens": prompt_tokens,
            "outputTokens": completion_tokens,
        }
        return {k: v for k, v in mapped.items() if isinstance(v, int)}

    return None


def invoke_with_fallback(model_id: str, prompt: str, *, temperature: float = 0.2) -> Dict[str, Any]:
    """Invoke a Bedrock model but provide a deterministic fallback."""

    try:
        client = BedrockClient()
        payload = _build_payload(model_id, prompt, temperature, max_tokens=600)
        raw_response = client.invoke(model_id, payload)
        text = _extract_text(model_id, raw_response)

        normalized: Dict[str, Any] = {"output": {"text": text or ""}}
        usage = _extract_usage(raw_response)
        if usage:
            normalized["usage"] = usage
        normalized["raw"] = raw_response

        if not text:
            normalized["output"]["text"] = ""

        return normalized
    except BedrockInvocationError:
        # Bedrock is optional for the hackathon experience. If credentials are
        # not present we fall back to a stub response that mimics Claude's JSON.
        return {
            "output": {
                "text": "Hackathon fallback: unable to reach Bedrock."
            },
            "usage": {"inputTokens": 0, "outputTokens": 0},
        }
