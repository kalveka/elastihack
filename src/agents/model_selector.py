"""Model selection agent powered by Claude 3 Sonnet."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
from .bedrock_client import BedrockClient, BedrockInvocationError, invoke_with_fallback


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
DEFAULT_ORDER = {candidate["id"]: index for index, candidate in enumerate(DEFAULT_CANDIDATES)}

SUPPORTED_MODEL_PREFIXES: Tuple[str, ...] = ("anthropic.", "mistral.", "meta.")
PROVIDER_RANKS = {
    "Anthropic": 3,
    "Mistral AI": 2,
    "Meta": 1,
}


PROMPT_TEMPLATE = """
You are a governance aware AI architect curating benchmarking prompts.
Here is the user's prompt:\n{prompt}\n
They describe the business and compliance requirements as JSON:\n{requirements}\n
Here is contextual knowledge from Elasticsearch:\n{context}\n
Here are model attribute records from the catalog:\n{model_attributes}\n
Bedrock availability snapshot:\n{bedrock_models}\n
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


def _normalize_bedrock_model(
    summary: Dict[str, Any],
    attributes_by_id: Dict[str, Dict[str, Any]],
    attributes_by_name: Dict[str, Dict[str, Any]],
    *,
    fallback_index: int,
) -> Dict[str, Any]:
    """Shape Bedrock model summaries into the candidate schema."""

    model_id = summary.get("modelId") or summary.get("modelArn")
    if not isinstance(model_id, str):
        model_id = f"bedrock-model-{fallback_index}"

    model_name = summary.get("modelName")
    if not isinstance(model_name, str):
        attr_match = attributes_by_id.get(model_id)
        if attr_match:
            model_name = attr_match.get("name")
    if not isinstance(model_name, str):
        model_name = model_id

    attr_match = attributes_by_id.get(model_id)
    if not attr_match:
        attr_match = attributes_by_name.get(model_name.lower()) if isinstance(model_name, str) else None

    candidate_defaults: Optional[Dict[str, Any]] = None
    if isinstance(model_id, str) and model_id in DEFAULT_BY_ID:
        candidate_defaults = DEFAULT_BY_ID[model_id]
    elif isinstance(model_name, str) and model_name.lower() in DEFAULT_BY_NAME:
        candidate_defaults = DEFAULT_BY_NAME[model_name.lower()]

    strengths = (attr_match or {}).get("strengths") or (candidate_defaults or {}).get("strengths", [])
    cost = (attr_match or {}).get("cost") or (candidate_defaults or {}).get("cost")
    score = (attr_match or {}).get("score")
    provider_name = summary.get("providerName")
    if not isinstance(score, (int, float)):
        score = PROVIDER_RANKS.get(provider_name, 0)

    summary_text = (attr_match or {}).get("summary") or summary.get("description")
    attr_tags = (attr_match or {}).get("tags", [])
    tags: List[str] = []
    for tag in attr_tags:
        if isinstance(tag, str) and tag not in tags:
            tags.append(tag)

    return {
        "id": model_id,
        "name": model_name,
        "summary": summary_text,
        "tags": tags,
        "category": summary.get("modelClass") or (attr_match or {}).get("category"),
        "cost": cost,
        "strengths": strengths,
        "score": score,
        "provider": provider_name,
        "input_modalities": summary.get("inputModalities") or [],
        "output_modalities": summary.get("outputModalities") or [],
        "inference_modes": summary.get("inferenceTypesSupported") or [],
        "customizations": summary.get("customizationsSupported") or [],
        "lifecycle": summary.get("modelLifecycle"),
        "source": "bedrock",
    }


def _candidate_sort_key(candidate: Dict[str, Any]) -> Tuple[int, int, int, str]:
    """Deterministic ordering favouring curated defaults, score, and provider."""

    model_id = candidate.get("id") or candidate.get("model_id")
    default_rank = DEFAULT_ORDER.get(model_id, len(DEFAULT_ORDER))
    score = candidate.get("score")
    if not isinstance(score, (int, float)):
        score = 0
    provider_rank = PROVIDER_RANKS.get(candidate.get("provider"), 0)
    name = candidate.get("name") or candidate.get("model_name") or ""
    if not isinstance(name, str):
        name = ""

    return (
        default_rank,
        -int(score * 100 if isinstance(score, float) else score),
        -provider_rank,
        name.lower(),
    )


def _snapshot_bedrock_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reduce Bedrock model summaries to a JSON-serializable form for prompting."""

    snapshot: List[Dict[str, Any]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        lifecycle = item.get("modelLifecycle")
        lifecycle_status = None
        if isinstance(lifecycle, dict):
            lifecycle_status = lifecycle.get("status")
        snapshot.append(
            {
                "modelId": item.get("modelId") or item.get("modelArn"),
                "modelName": item.get("modelName"),
                "providerName": item.get("providerName"),
                "outputModalities": item.get("outputModalities"),
                "inferenceTypesSupported": item.get("inferenceTypesSupported"),
                "customizationsSupported": item.get("customizationsSupported"),
                "modelClass": item.get("modelClass"),
                "lifecycleStatus": lifecycle_status,
            }
        )
    return snapshot


def _summarize_bedrock_error(message: str) -> str:
    """Provide a user-readable hint for common Bedrock catalog failures."""

    lowered = message.lower()
    if "accessdenied" in lowered or "not authorized" in lowered:
        return "Access denied when querying Bedrock catalog; verify IAM permissions."
    if "expiredtoken" in lowered or "token expired" in lowered:
        return "AWS session token expired; refresh Bedrock credentials."
    if "could not connect" in lowered or "timed out" in lowered:
        return "Unable to reach Bedrock endpoint; check network connectivity."
    return message


CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _parse_selector_output(text: str) -> Dict[str, Any]:
    """Attempt to parse the selector response into JSON."""

    if not isinstance(text, str):
        raise ValueError("Non-string response received from model selector.")

    match = CODE_BLOCK_PATTERN.search(text)
    candidate = match.group(1) if match else text
    decoder = json.JSONDecoder()

    def _try_decode(start_idx: int) -> Optional[Dict[str, Any]]:
        try:
            payload, end = decoder.raw_decode(candidate, start_idx)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            # Sometimes models wrap the object in a single-element list.
            for item in payload:
                if isinstance(item, dict):
                    return item
            return {"candidate_models": payload}
        # Ignore other types (strings, numbers).
        return None

    for index, char in enumerate(candidate):
        if char not in "{[":
            continue
        parsed = _try_decode(index)
        if parsed is not None:
            return parsed

    raise ValueError("Unable to locate JSON object in model selector response.")


def _prepare_candidates(
    model_attributes: List[Dict[str, Any]],
    bedrock_models: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Derive a ranked list of candidate models from catalog entries."""

    parsed = [
        _normalize_model_attribute(doc, fallback_index=index + 1)
        for index, doc in enumerate(model_attributes)
    ]

    attributes_by_id = {
        item["id"]: item for item in parsed if isinstance(item.get("id"), str)
    }
    attributes_by_name = {
        item["name"].lower(): item
        for item in parsed
        if isinstance(item.get("name"), str)
    }

    candidates: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, summary in enumerate(bedrock_models):
        model_id = summary.get("modelId")
        if not isinstance(model_id, str):
            model_id = summary.get("modelArn")
        if not isinstance(model_id, str):
            model_id = f"bedrock-model-{index + 1}"

        if not any(model_id.startswith(prefix) for prefix in SUPPORTED_MODEL_PREFIXES):
            continue

        candidate = _normalize_bedrock_model(
            summary,
            attributes_by_id,
            attributes_by_name,
            fallback_index=index + 1,
        )
        candidate_id = candidate.get("id")
        if isinstance(candidate_id, str) and candidate_id not in seen_ids:
            candidates.append(candidate)
            seen_ids.add(candidate_id)

    if not candidates:
        for item in parsed:
            candidate_id = item.get("id")
            if not isinstance(candidate_id, str):
                continue
            if not any(candidate_id.startswith(prefix) for prefix in SUPPORTED_MODEL_PREFIXES):
                continue
            if candidate_id in seen_ids:
                continue
            candidate_copy = dict(item)
            candidate_copy.setdefault("source", "model-attributes")
            candidates.append(candidate_copy)
            seen_ids.add(candidate_id)

    if not candidates:
        return [dict(item) for item in DEFAULT_CANDIDATES]

    candidates.sort(key=_candidate_sort_key)
    return candidates


def _compose_sample_prompt(user_prompt: str) -> str:
    """Generate a compliance-focused sample prompt derived from the user request."""

    return (
        f"{user_prompt.strip()}\n\n"
        "When responding, provide:\n"
        "1. Compliance guardrails and risk mitigations that apply.\n"
        "2. Relevant industry or regional regulatory obligations.\n"
        "3. Quality assurance steps before deployment."
    )


def _default_recommendation(
    prompt: str,
    candidates: List[Dict[str, Any]],
    *,
    bedrock_error: Optional[str] = None,
    catalog_count: int = 0,
) -> Dict[str, Any]:
    """Fallback structure populated from Bedrock catalog metadata."""

    def _describe_candidate(candidate: Dict[str, Any], position: int) -> Dict[str, Any]:
        model_id = candidate.get("id") or candidate.get("model_id")
        model_name = candidate.get("name") or candidate.get("model_name") or f"Model {position}"
        provider = candidate.get("provider") or "Unknown provider"
        strengths = candidate.get("strengths") or []
        strengths_text = ", ".join(strengths) if strengths else "general capabilities"
        reasoning = (
            f"Heuristic selection based on Bedrock metadata. Provider: {provider}. "
            f"Known strengths: {strengths_text}."
        )
        policy_notes = [
            "Review Bedrock catalog metadata and internal policies before production use.",
            "Validate the model against compliance and safety benchmarks relevant to this workload.",
        ]

        return {
            "model_id": model_id,
            "model_name": model_name,
            "sample_prompt": _compose_sample_prompt(prompt),
            "reasoning": reasoning,
            "policy_notes": policy_notes,
        }

    heuristic_candidates = [
        _describe_candidate(candidate, index + 1) for index, candidate in enumerate(candidates[:3])
    ]

    if not heuristic_candidates:
        heuristic_candidates = [_describe_candidate(default, index + 1) for index, default in enumerate(DEFAULT_CANDIDATES[:3])]

    recommended = heuristic_candidates[0]

    governance_notes = [
        "Model selector JSON parsing failed; returning heuristic ranking based on Bedrock catalog metadata."
    ]
    if bedrock_error:
        governance_notes.append(f"Bedrock catalog warning: {bedrock_error}")

    fallback_payload = {
        "candidate_models": heuristic_candidates,
        "recommended_model": {
            "model_id": recommended["model_id"],
            "model_name": recommended["model_name"],
            "reasoning": recommended["reasoning"],
            "alignment": "Heuristic selection prioritizing governance alignment and provider reputation.",
        },
        "governance_notes": governance_notes,
    }
    fallback_payload["bedrock_status"] = {
        "catalog_count": catalog_count,
        "error": bedrock_error,
    }
    return fallback_payload


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
        bedrock_catalog: List[Dict[str, Any]] = []
        bedrock_error: Optional[str] = None
        try:
            bedrock_catalog = BedrockClient().list_available_models()
        except BedrockInvocationError as exc:
            full_error = str(exc)
            bedrock_error = _summarize_bedrock_error(full_error)
            logger.warning("Bedrock catalog query failed: %s", full_error)
        except Exception as exc:  # pragma: no cover - defensive
            full_error = str(exc)
            bedrock_error = _summarize_bedrock_error(full_error)
            logger.warning("Unexpected Bedrock catalog error: %s", full_error)
        candidates = _prepare_candidates(model_attributes, bedrock_catalog)
        fallback_structure = _default_recommendation(
            prompt,
            candidates,
            bedrock_error=bedrock_error,
            catalog_count=len(bedrock_catalog),
        )
        bedrock_snapshot = _snapshot_bedrock_models(bedrock_catalog)
        payload_prompt = PROMPT_TEMPLATE.format(
            prompt=prompt,
            requirements=json.dumps(requirements, indent=2),
            context=json.dumps(context, indent=2),
            model_attributes=json.dumps(model_attributes, indent=2),
            bedrock_models=json.dumps(bedrock_snapshot, indent=2, default=str),
            candidates=json.dumps(candidates, indent=2),
        )
        response = invoke_with_fallback(self.model_id, payload_prompt)

        text = response.get("output", {}).get("text")
        if not text:
            fallback_structure["governance_notes"].append(
                "Model selector returned an empty response; falling back to defaults."
            )
            fallback_structure["bedrock_status"]["error"] = "Model selector returned empty response."
            return fallback_structure

        parse_error: Optional[str] = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = _parse_selector_output(text)
            except ValueError as exc:
                parse_error = str(exc)
            except json.JSONDecodeError as exc:
                parse_error = f"Invalid JSON from model selector: {exc}"

        if parse_error:
            logger.warning("Model selector response parsing failed: %s", parse_error)
            fallback_structure["governance_notes"].append(
                f"Model selector response was not valid JSON: {parse_error}"
            )
            fallback_structure["bedrock_status"]["error"] = parse_error
            fallback_structure["bedrock_status"]["catalog_count"] = len(bedrock_catalog)
            fallback_structure["raw_selector_output"] = text
            return fallback_structure

        if isinstance(parsed, list):
            parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else None
            if parsed is None:
                parse_error = "Model selector returned a top-level list without an object payload."

        if parse_error:
            logger.warning("Model selector response parsing failed: %s", parse_error)
            fallback_structure["governance_notes"].append(
                f"Model selector response was not valid JSON: {parse_error}"
            )
            fallback_structure["bedrock_status"]["error"] = parse_error
            fallback_structure["bedrock_status"]["catalog_count"] = len(bedrock_catalog)
            fallback_structure["raw_selector_output"] = text
            return fallback_structure

        if not isinstance(parsed, dict):
            fallback_structure["governance_notes"].append(
                "Model selector returned an unexpected payload; falling back to defaults."
            )
            fallback_structure["bedrock_status"]["error"] = "Model selector returned non-dict payload."
            fallback_structure["bedrock_status"]["catalog_count"] = len(bedrock_catalog)
            fallback_structure["raw_selector_output"] = text
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
        status = parsed.get("bedrock_status")
        if not isinstance(status, dict):
            status = {}
            parsed["bedrock_status"] = status

        status.setdefault("catalog_count", len(bedrock_catalog))
        if bedrock_error and "error" not in status:
            status["error"] = bedrock_error
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
