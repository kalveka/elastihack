"""Combine internal and external context streams."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def aggregate(
    elastic_docs: List[Dict[str, Any]],
    research_docs: List[Dict[str, Any]],
    model_attribute_docs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Merge context streams with traceability metadata."""

    model_attribute_docs = model_attribute_docs or []

    return {
        "elastic": [
            {
                "id": doc.get("id"),
                "title": doc.get("title"),
                "excerpt": (doc.get("highlight") or [doc.get("body", "")])[0:1],
                "score": doc.get("score"),
                "category": doc.get("category"),
                "source": doc.get("source") or "elastic",
                "last_updated": doc.get("last_updated"),
                "tags": doc.get("tags", []),
            }
            for doc in elastic_docs
        ],
        "research": [
            {
                "title": doc.get("title"),
                "summary": doc.get("abstract") or doc.get("summary"),
                "url": doc.get("url"),
                "source": doc.get("source", "research"),
            }
            for doc in research_docs
        ],
        "model_attributes": [
            {
                "id": doc.get("id"),
                "title": doc.get("title"),
                "summary": doc.get("body"),
                "tags": doc.get("tags", []),
                "category": doc.get("category"),
                "source": doc.get("source") or "model-attributes",
                "last_updated": doc.get("last_updated"),
                "score": doc.get("score"),
            }
            for doc in model_attribute_docs
        ],
    }
