"""Thin wrapper around the AWS Bedrock runtime for hackathon demos."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError


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
        except (NoCredentialsError, BotoCoreError) as exc:  # pragma: no cover - passthrough to fallback
            raise BedrockInvocationError(str(exc)) from exc

        body = response.get("body")
        if hasattr(body, "read"):
            data = body.read().decode("utf-8")
        else:
            data = body
        return json.loads(data)


def invoke_with_fallback(model_id: str, prompt: str, *, temperature: float = 0.2) -> Dict[str, Any]:
    """Invoke a Bedrock model but provide a deterministic fallback."""

    try:
        client = BedrockClient()
        payload = {
            "inputText": prompt,
            "textGenerationConfig": {"temperature": temperature, "maxTokenCount": 512},
        }
        return client.invoke(model_id, payload)
    except BedrockInvocationError:
        # Bedrock is optional for the hackathon experience. If credentials are
        # not present we fall back to a stub response that mimics Claude's JSON.
        return {
            "output": {
                "text": "Hackathon fallback: unable to reach Bedrock."
            },
            "usage": {"inputTokens": 0, "outputTokens": 0},
        }
