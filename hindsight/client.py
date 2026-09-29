"""
Hindsight Memory Client
=======================
Implements retain(), recall(), and reflect() using:
  - Remote Hindsight REST API (if HINDSIGHT_API_KEY is set)
  - Local ChromaDB fallback (default for hackathon / offline dev)

Both backends expose the same interface so the rest of the app is unchanged.
"""
from __future__ import annotations

import json
import hashlib
from abc import ABC, abstractmethod
from typing import Optional

import httpx
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import (
    HINDSIGHT_API_KEY,
    HINDSIGHT_BASE_URL,
    CHROMA_PERSIST_DIR,
    USE_LOCAL_HINDSIGHT,
)


# ═══════════════════════════════════════════════════════════════════════
# Abstract Base
# ═══════════════════════════════════════════════════════════════════════

class HindsightBase(ABC):
    """Interface every Hindsight backend must implement."""

    @abstractmethod
    def retain(self, documents: list[dict]) -> dict:
        """
        Store documents in memory.
        Each document: {"id": str, "text": str, "metadata": dict}
        Returns: {"stored": int, "status": "ok"}
        """
        ...

    @abstractmethod
    def recall(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        Retrieve documents similar to query.
        Returns list of {"id", "text", "metadata", "score"}.
        """
        ...

    @abstractmethod
    def reflect(self, topic: str, n_source_docs: int = 20) -> str:
        """
        Synthesize a higher-level observation from stored knowledge.
        Returns a summary string (the 'mental model').
        """
        ...


# ═══════════════════════════════════════════════════════════════════════
# Local ChromaDB Backend
# ═══════════════════════════════════════════════════════════════════════

class LocalHindsight(HindsightBase):
    """
    Local implementation using ChromaDB for vector storage.
    Perfect for hackathon dev — no external API needed.
    """

    def __init__(self, collection_name: str = "invoice_agent_memory"):
        self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._collection_name = collection_name

    @property
    def count(self) -> int:
        return self._collection.count()

    def retain(self, documents: list[dict]) -> dict:
        """Store documents into ChromaDB."""
        if not documents:
            return {"stored": 0, "status": "no_documents"}

        ids = []
        texts = []
        metadatas = []

        for doc in documents:
            doc_id = doc.get("id") or hashlib.md5(doc["text"].encode()).hexdigest()[:12]
            ids.append(doc_id)
            texts.append(doc["text"])
            metadatas.append(doc.get("metadata", {}))

        # Upsert to handle re-ingestion gracefully
        self._collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        return {"stored": len(ids), "status": "ok", "collection": self._collection_name}

    def recall(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Retrieve similar documents via semantic search."""
        kwargs: dict = {
            "query_texts": [query],
            "n_results": min(n_results, self._collection.count() or 1),
        }
        if filters:
            kwargs["where"] = filters

        results = self._collection.query(**kwargs)

        docs = []
        for i in range(len(results["ids"][0])):
            docs.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": round(1 - results["distances"][0][i], 4),  # cosine similarity
            })
        return docs

    def reflect(self, topic: str, n_source_docs: int = 20) -> str:
        """
        Build a mental model by retrieving relevant docs and synthesizing.
        In local mode, we concatenate the top results and create a summary template.
        (In production, this would call an LLM for synthesis.)
        """
        docs = self.recall(topic, n_results=n_source_docs)
        if not docs:
            return f"No stored knowledge found for topic: {topic}"

        # Group by metadata type
        by_type: dict[str, list] = {}
        for d in docs:
            dtype = d["metadata"].get("type", "unknown")
            by_type.setdefault(dtype, []).append(d)

        lines = [f"=== Mental Model: {topic} ===\n"]
        lines.append(f"Based on {len(docs)} relevant records:\n")

        for dtype, items in by_type.items():
            lines.append(f"\n--- {dtype.replace('_', ' ').title()} ({len(items)} records) ---")
            for item in items[:5]:
                snippet = item["text"][:200].replace("\n", " ")
                lines.append(f"  • [{item['id']}] (relevance: {item['score']:.2f}) {snippet}...")

        # Extract key patterns
        vendors_mentioned = set()
        decisions = []
        for d in docs:
            v = d["metadata"].get("vendor")
            if v:
                vendors_mentioned.add(v)
            dec = d["metadata"].get("decision")
            if dec:
                decisions.append(dec)

        if vendors_mentioned:
            lines.append(f"\nVendors involved: {', '.join(sorted(vendors_mentioned))}")
        if decisions:
            from collections import Counter
            dc = Counter(decisions)
            lines.append(f"Decision distribution: {dict(dc)}")

        return "\n".join(lines)

    def reset(self):
        """Clear all stored data (for testing)."""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )


# ═══════════════════════════════════════════════════════════════════════
# Remote Hindsight API Backend
# ═══════════════════════════════════════════════════════════════════════

class RemoteHindsight(HindsightBase):
    """
    REST API client for a remote Hindsight service.
    Endpoints expected:
      POST /retain   — store documents
      POST /recall   — semantic search
      POST /reflect  — synthesize mental model
    """

    def __init__(self):
        self._base_url = HINDSIGHT_BASE_URL.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {HINDSIGHT_API_KEY}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=30.0)

    def retain(self, documents: list[dict]) -> dict:
        resp = self._client.post(
            f"{self._base_url}/retain",
            headers=self._headers,
            json={"documents": documents},
        )
        resp.raise_for_status()
        return resp.json()

    def recall(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        payload = {"query": query, "n_results": n_results}
        if filters:
            payload["filters"] = filters

        resp = self._client.post(
            f"{self._base_url}/recall",
            headers=self._headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def reflect(self, topic: str, n_source_docs: int = 20) -> str:
        resp = self._client.post(
            f"{self._base_url}/reflect",
            headers=self._headers,
            json={"topic": topic, "n_source_docs": n_source_docs},
        )
        resp.raise_for_status()
        return resp.json().get("reflection", "")


# ═══════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════

def get_hindsight_client() -> HindsightBase:
    """Return the appropriate Hindsight backend."""
    if USE_LOCAL_HINDSIGHT or not HINDSIGHT_API_KEY:
        return LocalHindsight()
    return RemoteHindsight()
