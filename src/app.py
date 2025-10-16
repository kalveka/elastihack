"""FastAPI application orchestrating the meta-agent pipeline."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.context_fetcher import ElasticContextFetcher, safe_fetch
from agents.context_aggregator import aggregate
from agents.model_selector import ModelSelector
from agents.judge import Judge
from agents.research_fetcher import ResearchFetcher

load_dotenv()

app = FastAPI(title="Azion Meta-Agent", version="0.1.0")


class RequirementProfile(BaseModel):
    industry: Optional[str] = Field(default=None, description="Industry vertical")
    data_sensitivity: Optional[str] = Field(
        default="internal", description="Data classification for the workload"
    )
    regulatory_frameworks: list[str] = Field(
        default_factory=list, description="Applicable regulations"
    )
    latency_tolerance_ms: Optional[int] = Field(
        default=None, description="Max acceptable latency"
    )
    budget_tier: Optional[str] = Field(
        default="medium", description="Cost sensitivity (low/medium/high)"
    )


class MetaAgentRequest(BaseModel):
    prompt: str
    requirements: RequirementProfile = Field(default_factory=RequirementProfile)
    max_context: int = Field(default=3, ge=1, le=10)


class MetaAgentResponse(BaseModel):
    recommendation: Dict[str, Any]
    judge: Dict[str, Any]
    context: Dict[str, Any]


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/meta-agent", response_model=MetaAgentResponse)
def meta_agent(request: MetaAgentRequest) -> MetaAgentResponse:
    """Run the full pipeline using Elastic, Claude, and Mixtral."""

    try:
        fetcher = ElasticContextFetcher()
        elastic_docs = fetcher.fetch(request.prompt, limit=request.max_context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # Fall back to safe fetch which will handle credentials issues gracefully.
        elastic_docs = safe_fetch(request.prompt, limit=request.max_context)

    research_docs = ResearchFetcher().fetch(request.prompt)
    context = aggregate(elastic_docs, research_docs)

    selector = ModelSelector()
    recommendation = selector.choose_model(
        request.prompt, request.requirements.model_dump(), context
    )

    judge = Judge()
    evaluation = judge.evaluate(request.prompt, recommendation, context)

    return MetaAgentResponse(
        recommendation=recommendation,
        judge=evaluation,
        context=context,
    )


if __name__ == "__main__":  # pragma: no cover - convenience for local dev
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
