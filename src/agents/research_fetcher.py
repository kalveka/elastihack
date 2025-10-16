"""Placeholder for external research retrieval."""

from __future__ import annotations

from typing import Any, Dict, List


class ResearchFetcher:
    """Minimal stub that returns an empty list for hackathon use."""

    def fetch(self, prompt: str, *, limit: int = 3) -> List[Dict[str, Any]]:
        # In a full build we would call out to Semantic Scholar or similar.
        # For the hackathon demo we simply return an empty list so that the
        # pipeline remains functional without external API dependencies.
        return []
