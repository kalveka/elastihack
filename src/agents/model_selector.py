"""Model selection agent powered by Claude 3 Sonnet."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .bedrock_client import invoke_with_fallback


CANDIDATE_MODELS = [
    {
        "id": "anthropic.claude-3-sonnet-20240229-v1:0",
        "name": "Claude 3 Sonnet",
        "strengths": ["compliance reasoning", "structured output"],
        "cost": "high",
    },
    {
        "id": "meta.llama3-70b-instruct-v1:0",
        "name": "Llama3 70B Instruct",
        "strengths": ["general generation", "multilingual"],
        "cost": "medium",
    },
    {
        "id": "mistral.mixtral-8x7b-instruct-v0:1",
        "name": "Mixtral 8x7B",
        "strengths": ["fast iteration", "good judge"],
        "cost": "medium",
    },
]


PROMPT_TEMPLATE = """
You are a governance aware AI architect. A user needs help selecting a model.
Here is the user's prompt:\n{prompt}\n
They describe the business and compliance requirements as JSON:\n{requirements}\n
Here is contextual knowledge from Elasticsearch:\n{context}\n
Return a JSON object with keys model_name, model_id, reasoning, and policy_notes.
Only choose from the candidate models below:\n{candidates}\n""".strip()


class ModelSelector:
    """Coordinate prompt crafting and Bedrock invocation."""

    def __init__(self) -> None:
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    def choose_model(self, prompt: str, requirements: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        payload_prompt = PROMPT_TEMPLATE.format(
            prompt=prompt,
            requirements=json.dumps(requirements, indent=2),
            context=json.dumps(context, indent=2),
            candidates=json.dumps(CANDIDATE_MODELS, indent=2),
        )
        response = invoke_with_fallback(self.model_id, payload_prompt)

        text = response.get("output", {}).get("text")
        if not text:
            return {
                "model_name": "Mixtral 8x7B (fallback)",
                "model_id": "mistral.mixtral-8x7b-instruct-v0:1",
                "reasoning": "Unable to reach Bedrock, defaulting to Mixtral for offline demo.",
                "policy_notes": [
                    "Verify compliance context manually before executing sensitive workloads."
                ],
            }

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {
                "model_name": "Claude 3 Sonnet",
                "model_id": self.model_id,
                "reasoning": text,
                "policy_notes": [
                    "Claude suggested the response but it was not valid JSON; inspect manually."
                ],
            }
        return parsed
