"""Utilities for fetching compliance context from Elasticsearch."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests


class ElasticContextFetcher:
    """Retrieve governance and compliance snippets from an Elasticsearch index."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        index: Optional[str] = None,
    ) -> None:
        self.base_url = base_url or os.getenv("ELASTIC_URL")
        self.api_key = api_key or os.getenv("ELASTIC_API_KEY")
        self.username = username or os.getenv("ELASTIC_USERNAME")
        self.password = password or os.getenv("ELASTIC_PASSWORD")
        self.index = index or os.getenv("ELASTIC_INDEX", "compliance-docs")

        if not self.base_url:
            raise ValueError(
                "An Elasticsearch base URL is required. Set ELASTIC_URL or pass base_url."
            )

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        return headers

    def fetch(self, prompt: str, *, limit: int = 3) -> List[Dict[str, Any]]:
        """Perform a semantic-like query using a simple multi-match request."""

        search_url = f"{self.base_url.rstrip('/')}/{self.index}/_search"
        query = {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": prompt,
                    "fields": ["title^3", "body", "tags"],
                }
            },
            "highlight": {"fields": {"body": {}}},
        }

        auth: Optional[Any] = None
        if self.username and self.password:
            auth = (self.username, self.password)

        response = requests.post(search_url, headers=self._headers(), auth=auth, data=json.dumps(query), timeout=15)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        documents: List[Dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source", {})
            documents.append(
                {
                    "id": hit.get("_id"),
                    "title": source.get("title"),
                    "body": source.get("body"),
                    "tags": source.get("tags", []),
                    "score": hit.get("_score"),
                    "highlight": hit.get("highlight", {}).get("body", []),
                }
            )

        return documents


def safe_fetch(prompt: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    """Wrapper that swallows Elasticsearch errors and returns an empty list."""

    try:
        fetcher = ElasticContextFetcher()
        return fetcher.fetch(prompt, limit=limit)
    except Exception:
        return []
