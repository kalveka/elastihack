# 🧠 Azion Context Agents

## Overview
This document defines the agents that power the **Azion Context API**, which retrieves critical compliance context and external research to inform model selection and evaluation within the Azion platform.

Each agent operates as a serverless function or microservice, and together they enable dynamic reasoning pipelines that enrich user prompts before invoking reasoning models such as **Claude 3 Sonnet** or **Mixtral 8x7B**.

---

## Agent Roles

### 1. Context Fetcher (Elastic)
**Purpose:** Retrieve critical internal compliance, risk, and security context from the Elastic Stack.

- **Inputs:**  
  - `prompt` (string) — user business question or system request  
- **Outputs:**  
  - `elastic_context` (array of documents)  
- **Behavior:**  
  - Queries designated Elastic indices (e.g., `compliance-docs`, `security-controls`, `risk-register`)  
  - Filters and returns up to N relevant documents ranked by relevance score  
- **Policies:**  
  - Must sanitize and redact sensitive fields prior to downstream use  
  - Only query indices whitelisted under `EULA::ApprovedIndexes`

---

### 2. Research Fetcher
**Purpose:** Retrieve relevant external research or whitepapers from trusted APIs (e.g., Semantic Scholar, arXiv).

- **Inputs:**  
  - `prompt` (string)  
- **Outputs:**  
  - `research_context` (array of papers)  
- **Behavior:**  
  - Performs semantic search using the business prompt  
  - Returns concise metadata (title, abstract, URL, authors)  
- **Policies:**  
  - Limit results to 3–5 papers per query  
  - Must use public or licensed sources only  

---

### 3. Context Aggregator
**Purpose:** Merge multiple context streams into a unified payload for reasoning models.

- **Inputs:**  
  - `elastic_context`  
  - `research_context`  
- **Outputs:**  
  - `context` object with combined data  
- **Behavior:**  
  - Performs lightweight deduplication and normalization  
  - Annotates context source for traceability  

---

### 4. Model Selector (Claude 3 Sonnet)
**Purpose:** Select the most appropriate model for the downstream reasoning task.

- **Inputs:**  
  - `prompt` (business request)  
  - `context` (aggregated data)  
- **Outputs:**  
  - JSON with fields:  
    - `model_name` (string)  
    - `reasoning` (string)  
- **Behavior:**  
  - Applies multi-factor decision logic based on:  
    - Task type (text, multimodal, embedding, generation)  
    - Sensitivity (compliance-critical vs. experimental)  
    - Performance and cost constraints  
  - Returns recommended model and justification  

---

### 5. Judge (Mixtral 8x7B)
**Purpose:** Evaluate generated model outputs for factual accuracy, compliance adherence, and tone quality.

- **Inputs:**  
  - `response` (from selected model)  
  - `context` (reference data)  
- **Outputs:**  
  - `evaluation` (object containing scores and verdicts)  
- **Behavior:**  
  - Performs rubric-based assessment using structured output schema  
  - Emits transparent reasoning and confidence score  

---

## Data Flow Summary

```mermaid
flowchart LR
  A[User Prompt] --> B[Context Fetcher (Elastic)]
  A --> C[Research Fetcher]
  B & C --> D[Context Aggregator]
  D --> E[Claude 3 Sonnet - Model Selector]
  E --> F[Mixtral 8x7B - Judge]
  F --> G[Frontend / API Response]
```

## Governance Notes

- All agents must comply with Azion’s internal AI EULA and Data Classification Policy.
- No agent may send customer or personal data to non-approved endpoints.
- Logs are anonymized and retained per internal retention policy.
- All external API usage must align with corporate license terms and export restrictions.
- Future Extensions
- Add “Knowledge Synthesizer” agent to build longer-term summaries from prior prompts.
- Extend compliance fetcher to support Confluence and Jira sources.
- Add retrieval caching layer for performance optimization.

