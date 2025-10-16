"""Model selection agent powered by Claude 3 Sonnet."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .bedrock_client import invoke_with_fallback


DEFAULT_CANDIDATES = [
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

DEFAULT_BY_NAME = {item["name"].lower(): item for item in DEFAULT_CANDIDATES}
DEFAULT_BY_ID = {item["id"]: item for item in DEFAULT_CANDIDATES}


PROMPT_TEMPLATE = """
You are a governance aware AI architect curating benchmarking prompts.
Here is the user's prompt:\n{prompt}\n
They describe the business and compliance requirements as JSON:\n{requirements}\n
Here is contextual knowledge from Elasticsearch:\n{context}\n
Here are model attribute records from the catalog:\n{model_attributes}\n
Candidate models detected for consideration:\n{candidates}\n
Select the three most relevant candidate models for this workload. For each selected model craft
a tailored sample prompt that will stress-test the model on compliance and quality dimensions.
Return JSON with the following structure:
{{
  "candidate_models": [
    {{
      "model_id": "...",
      "model_name": "...",
      "sample_prompt": "...",
      "reasoning": "...",
      "policy_notes": ["...", "..."]
    }},
    (exactly three objects)
  ],
  "recommended_model": {{
    "model_id": "...",
    "model_name": "...",
    "reasoning": "...",
    "alignment": "brief description of why this selection meets governance needs"
  }},
  "governance_notes": ["...", "..."]
}}
Ensure each sample prompt maps to the user requirements and highlights any compliance sensitivities.
""".strip()


def _normalize_model_attribute(doc: Dict[str, Any], *, fallback_index: int) -> Dict[str, Any]:
    """Coerce catalog documents into a consistent model candidate record."""

    model_id = (
        doc.get("model_id")
        or doc.get("id")
        or doc.get("identifier")
        or f"fallback-model-{fallback_index}"
    )

    title = (
        doc.get("title")
        or doc.get("name")
        or doc.get("display_name")
        or f"Model {fallback_index}"
    )

    # Attempt to map to the default catalog when IDs do not look like Bedrock identifiers.
    candidate_defaults: Optional[Dict[str, Any]] = None
    if model_id in DEFAULT_BY_ID:
        candidate_defaults = DEFAULT_BY_ID[model_id]
    elif title.lower() in DEFAULT_BY_NAME:
        candidate_defaults = DEFAULT_BY_NAME[title.lower()]
    elif doc.get("tags"):
        for tag in doc["tags"]:
            if isinstance(tag, str) and tag.lower() in DEFAULT_BY_NAME:
                candidate_defaults = DEFAULT_BY_NAME[tag.lower()]
                break

    if candidate_defaults and not model_id.startswith(("anthropic.", "mistral.", "meta.")):
        model_id = candidate_defaults["id"]

    return {
        "id": model_id,
        "name": title,
        "summary": doc.get("summary") or doc.get("body"),
        "tags": doc.get("tags", []),
        "category": doc.get("category"),
        "cost": doc.get("cost") or (candidate_defaults or {}).get("cost"),
        "strengths": doc.get("strengths") or (candidate_defaults or {}).get("strengths", []),
        "score": doc.get("score"),
        "source": doc.get("source"),
    }


def _prepare_candidates(model_attributes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derive a ranked list of candidate models from catalog entries."""

    parsed = [
        _normalize_model_attribute(doc, fallback_index=index + 1)
        for index, doc in enumerate(model_attributes)
    ]

    # Sort by score when available, otherwise preserve input order.
    parsed.sort(key=lambda item: (item.get("score") is not None, item.get("score", 0)), reverse=True)
    if not parsed:
        return DEFAULT_CANDIDATES[:]

    return parsed


def _default_recommendation(prompt: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback structure when Bedrock is unreachable or returns invalid JSON."""

    top_candidates = []
    for index, candidate in enumerate(candidates[:3]):
        model_id = candidate.get("id") or candidate.get("model_id")
        model_name = candidate.get("name") or candidate.get("model_name") or f"Model {index + 1}"
        top_candidates.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "sample_prompt": prompt,
                "reasoning": "Fallback prompt reused due to Bedrock unavailability.",
                "policy_notes": [
                    "Validate compliance assumptions manually before production use."
                ],
            }
        )

    existing_ids = {item["model_id"] for item in top_candidates}
    for default in DEFAULT_CANDIDATES:
        if len(top_candidates) >= 3:
            break
        if default["id"] in existing_ids:
            continue
        top_candidates.append(
            {
                "model_id": default["id"],
                "model_name": default["name"],
                "sample_prompt": prompt,
                "reasoning": "Default candidate provided to ensure evaluation coverage.",
                "policy_notes": [
                    "Review catalog metadata manually because default candidate was injected."
                ],
            }
        )
        existing_ids.add(default["id"])

    recommended = top_candidates[0] if top_candidates else {
        "model_id": DEFAULT_CANDIDATES[0]["id"],
        "model_name": DEFAULT_CANDIDATES[0]["name"],
        "sample_prompt": prompt,
        "reasoning": "Defaulting to Claude 3 Sonnet for balanced governance performance.",
        "policy_notes": [
            "Fallback triggered because Bedrock invocation failed; verify manually."
        ],
    }

    return {
        "candidate_models": top_candidates,
        "recommended_model": {
            "model_id": recommended["model_id"],
            "model_name": recommended["model_name"],
            "reasoning": recommended["reasoning"],
            "alignment": "Fallback selection prioritizing governance coverage.",
        },
        "governance_notes": [
            "Bedrock invocation failed; ensure catalog recommendations are reviewed manually."
        ],
    }


class ModelSelector:
    """Coordinate prompt crafting and Bedrock invocation."""

    def __init__(self) -> None:
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    def choose_model(
        self,
        prompt: str,
        requirements: Dict[str, Any],
        context: Dict[str, Any],
        model_attributes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        candidates = _prepare_candidates(model_attributes)
        fallback_structure = _default_recommendation(prompt, candidates)
        payload_prompt = PROMPT_TEMPLATE.format(
            prompt=prompt,
            requirements=json.dumps(requirements, indent=2),
            context=json.dumps(context, indent=2),
            model_attributes=json.dumps(model_attributes, indent=2),
            candidates=json.dumps(candidates, indent=2),
        )
        response = invoke_with_fallback(self.model_id, payload_prompt)

        text = response.get("output", {}).get("text")
        if not text:
            return fallback_structure

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return fallback_structure

        raw_candidates = parsed.get("candidate_models")
        sanitized_candidates: List[Dict[str, Any]] = []
        fallback_candidates = fallback_structure["candidate_models"]
        if isinstance(raw_candidates, list):
            for index in range(3):
                fallback_candidate = fallback_candidates[index] if index < len(fallback_candidates) else fallback_candidates[0]
                if index < len(raw_candidates) and isinstance(raw_candidates[index], dict):
                    candidate = raw_candidates[index]
                    model_id = candidate.get("model_id") or candidate.get("id")
                    if not isinstance(model_id, str):
                        model_id = fallback_candidate["model_id"]
                    model_name = candidate.get("model_name") or candidate.get("name")
                    if not isinstance(model_name, str):
                        model_name = fallback_candidate["model_name"]
                    sample_prompt = candidate.get("sample_prompt") or fallback_candidate["sample_prompt"]
                    reasoning = candidate.get("reasoning") or fallback_candidate["reasoning"]
                    policy_notes = candidate.get("policy_notes")
                    if not isinstance(policy_notes, list):
                        policy_notes = fallback_candidate["policy_notes"]
                    sanitized_candidates.append(
                        {
                            "model_id": model_id,
                            "model_name": model_name,
                            "sample_prompt": sample_prompt,
                            "reasoning": reasoning,
                            "policy_notes": policy_notes,
                        }
                    )
                else:
                    sanitized_candidates.append(fallback_candidate)
        else:
            sanitized_candidates = fallback_candidates

        parsed["candidate_models"] = sanitized_candidates

        recommended = parsed.get("recommended_model")
        if not isinstance(recommended, dict):
            fallback = sanitized_candidates[0]
            parsed["recommended_model"] = {
                "model_id": fallback.get("model_id"),
                "model_name": fallback.get("model_name"),
                "reasoning": fallback.get("reasoning", "Selected as top-ranked fallback."),
                "alignment": "Derived from fallback candidate list.",
            }

        parsed.setdefault("governance_notes", [])
        return parsed

    def run_test_models(
        self,
        candidate_models: List[Dict[str, Any]],
        *,
        fallback_prompt: str,
    ) -> List[Dict[str, Any]]:
        """Invoke each selected candidate model with its tailored sample prompt."""

        results: List[Dict[str, Any]] = []
        for candidate in candidate_models[:3]:
            model_id = candidate.get("model_id") or candidate.get("id")
            if not isinstance(model_id, str):
                continue

            sample_prompt = candidate.get("sample_prompt") or fallback_prompt
            invocation = invoke_with_fallback(model_id, sample_prompt, temperature=0.3)
            output_text = invocation.get("output", {}).get("text", "")
            results.append(
                {
                    "model_id": model_id,
                    "model_name": candidate.get("model_name") or candidate.get("name") or model_id,
                    "sample_prompt": sample_prompt,
                    "output": output_text,
                    "usage": invocation.get("usage", {}),
                }
            )
        return results
