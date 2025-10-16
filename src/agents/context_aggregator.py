"""Combine internal and external context streams."""

from __future__ import annotations

from typing import Any, Dict, List


def aggregate(elastic_docs: List[Dict[str, Any]], research_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge context streams with traceability metadata."""

    return {
        "elastic": [
            {
                "id": doc.get("id"),
                "title": doc.get("title"),
                "excerpt": (doc.get("highlight") or [doc.get("body", "")])[0:1],
                "score": doc.get("score"),
                "source": "elastic",
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
    }
