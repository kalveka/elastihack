"""FastAPI application orchestrating the meta-agent pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from agents.context_fetcher import ElasticContextFetcher, safe_fetch
from agents.context_aggregator import aggregate
from agents.model_selector import ModelSelector
from agents.judge import Judge
from agents.research_fetcher import ResearchFetcher

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

app = FastAPI(title="Azion Meta-Agent", version="0.1.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


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
    test_runs: List[Dict[str, Any]] = Field(default_factory=list)


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def root(request: Request) -> HTMLResponse:
    if not TEMPLATE_DIR.exists():
        return HTMLResponse(
            content=(
                "Azion Meta-Agent service is running. "
                "Templates directory not found; visit /docs for API interaction."
            ),
            status_code=200,
        )

    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/meta-agent", include_in_schema=False)
def meta_agent_get() -> Dict[str, Any]:
    return {
        "message": "Use POST /meta-agent with JSON payload to run the pipeline.",
        "example": {
            "prompt": "Draft a customer onboarding assistant for EU banking.",
            "requirements": {
                "industry": "finance",
                "data_sensitivity": "restricted",
                "regulatory_frameworks": ["GDPR"],
            },
            "max_context": 3,
        },
    }


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/meta-agent", response_model=MetaAgentResponse)
def meta_agent(request: MetaAgentRequest) -> MetaAgentResponse:
    """Run the full pipeline using Elastic, Claude, and Mixtral."""

    try:
        fetcher = ElasticContextFetcher(index="internal-docs")
        elastic_docs = fetcher.fetch(request.prompt, limit=request.max_context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # Fall back to safe fetch which will handle credentials issues gracefully.
        elastic_docs = safe_fetch(request.prompt, limit=request.max_context, index="internal-docs")

    try:
        attribute_fetcher = ElasticContextFetcher(index="model-attributes")
        model_attribute_docs = attribute_fetcher.fetch(request.prompt, limit=5)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        model_attribute_docs = safe_fetch(request.prompt, limit=5, index="model-attributes")

    research_docs = ResearchFetcher().fetch(request.prompt)
    context = aggregate(elastic_docs, research_docs, model_attribute_docs)

    selector = ModelSelector()
    recommendation = selector.choose_model(
        request.prompt, request.requirements.model_dump(), context, model_attribute_docs
    )
    candidate_models = recommendation.get("candidate_models", [])
    test_runs = selector.run_test_models(candidate_models, fallback_prompt=request.prompt)

    judge = Judge()
    evaluation = judge.evaluate(
        request.prompt,
        recommendation,
        context,
        candidate_models=candidate_models,
        candidate_outputs=test_runs,
    )

    return MetaAgentResponse(
        recommendation=recommendation,
        judge=evaluation,
        context=context,
        test_runs=test_runs,
    )


if __name__ == "__main__":  # pragma: no cover - convenience for local dev
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
