"""Judge agent using Mixtral 8x7B."""

from __future__ import annotations

import json
from typing import Any, Dict

from .bedrock_client import invoke_with_fallback


EVALUATION_PROMPT = """
You are an impartial compliance judge. Given the user's prompt, the selected model,
its reasoning, and compliance context, decide if the recommendation is safe.
Respond in JSON with keys verdict (approve|caution|reject),
risks (array of strings), and suggestions (array of strings).

Prompt:\n{prompt}\n
Model Selection:\n{selection}\n
Compliance Context:\n{context}\n""".strip()


class Judge:
    """Run Mixtral in critique mode to score the decision."""

    def __init__(self) -> None:
        self.model_id = "mistral.mixtral-8x7b-instruct-v0:1"

    def evaluate(self, prompt: str, selection: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        payload_prompt = EVALUATION_PROMPT.format(
            prompt=prompt,
            selection=json.dumps(selection, indent=2),
            context=json.dumps(context, indent=2),
        )
        response = invoke_with_fallback(self.model_id, payload_prompt, temperature=0.1)
        text = response.get("output", {}).get("text")
        if not text:
            return {
                "verdict": "caution",
                "risks": ["Unable to obtain Mixtral review; perform manual validation."],
                "suggestions": ["Re-run once Bedrock credentials are configured."],
            }

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "verdict": "caution",
                "risks": [
                    "Mixtral returned non-JSON output. Double-check compliance dependencies."
                ],
                "suggestions": [text],
            }
