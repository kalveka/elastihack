# Azion Meta-Agent Hackathon App

This repository contains a lightweight FastAPI application that demonstrates how to
stitch together ElasticSearch context with AWS Bedrock models following the
sequence diagram provided in the prompt. The meta-agent lets users submit a prompt
plus compliance requirements, then:

1. Retrieves compliance snippets from ElasticSearch.
2. Aggregates research context (stubbed for hackathon speed).
3. Asks Claude 3 Sonnet on Bedrock to recommend a best-fit model.
4. Uses Mixtral 8x7B on Bedrock as a judge to flag any compliance risks.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.env .env  # update with your Elastic and AWS credentials
uvicorn app:app --reload --app-dir src
```

The interactive OpenAPI docs are available at <http://localhost:8000/docs>.

## Environment variables

| Variable | Description |
| --- | --- |
| `ELASTIC_URL` | Base URL for your ElasticSearch cluster (e.g. `https://example.es.amazonaws.com`) |
| `ELASTIC_API_KEY` | Optional API key for Elastic. |
| `ELASTIC_USERNAME` / `ELASTIC_PASSWORD` | Optional basic auth credentials. |
| `BEDROCK_REGION` | AWS region hosting Bedrock (defaults to `us-east-1`). |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials for Bedrock access. |

The service expects two Elastic indexes to be present: `internal-docs` for compliance
context and `model-attributes` for catalog metadata that informs model selection.

When AWS credentials are not supplied the application falls back to deterministic
stub responses, making it safe to demo without cloud access.

## Sequence alignment

The `src/app.py` endpoint orchestrates the agents defined under `src/agents` to
mirror the hackathon diagram:

```
User Prompt -> Elastic Context Fetcher -> Context Aggregator -> Claude Model Selector -> Mixtral Judge -> Response
```

Each component is intentionally small so teams can swap in production integrations
later (e.g. real research APIs, advanced scoring, persistence).

## Testing the pipeline

You can exercise the service locally with `curl`:

```bash
curl -X POST http://localhost:8000/meta-agent \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Draft a customer onboarding assistant for EU banking.",
    "requirements": {
      "industry": "finance",
      "data_sensitivity": "restricted",
      "regulatory_frameworks": ["GDPR", "EBA"],
      "latency_tolerance_ms": 500,
      "budget_tier": "high"
    }
  }'
```

The response contains the Elastic context sample, Claude's recommendation, and
Mixtral's compliance check.

## Limitations

- The research fetcher is stubbed to keep dependencies minimal.
- Bedrock calls require AWS credentials; otherwise the app returns fallback text.
- No persistence layer is provided—logging and analytics would be future work.
