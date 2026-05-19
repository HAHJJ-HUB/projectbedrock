"""ChromaDB-backed persistent memory for storing and retrieving research findings."""

import hashlib
import json
import os
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings

from config import MEMORY_PATH


def _get_client() -> chromadb.Client:
    os.makedirs(MEMORY_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=MEMORY_PATH)


def _collection(name: str):
    client = _get_client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def store_finding(
    content: str,
    source_url: str,
    agent: str,
    topic: str,
    metadata: Optional[dict] = None,
) -> str:
    collection = _collection("research_findings")
    doc_id = hashlib.md5(f"{source_url}:{content[:100]}".encode()).hexdigest()
    meta = {
        "source_url": source_url,
        "agent": agent,
        "topic": topic,
        "timestamp": datetime.utcnow().isoformat(),
        **(metadata or {}),
    }
    collection.upsert(documents=[content], ids=[doc_id], metadatas=[meta])
    return f"Stored finding from {source_url} (id={doc_id})"


def retrieve_findings(query: str, topic: str = "", n_results: int = 10) -> list[dict]:
    collection = _collection("research_findings")
    where = {"topic": topic} if topic else None
    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count() or 1),
            where=where,
        )
    except Exception:
        return []

    findings = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        findings.append({"content": doc, **meta})
    return findings


def get_all_sources(topic: str = "") -> list[str]:
    collection = _collection("research_findings")
    try:
        where = {"topic": topic} if topic else None
        results = collection.get(where=where)
        return list({m.get("source_url", "") for m in (results.get("metadatas") or [])})
    except Exception:
        return []


def store_source_map(topic: str, sources: list[dict]) -> None:
    collection = _collection("source_maps")
    doc_id = hashlib.md5(f"sourcemap:{topic}:{datetime.utcnow().date()}".encode()).hexdigest()
    collection.upsert(
        documents=[json.dumps(sources)],
        ids=[doc_id],
        metadatas=[{"topic": topic, "timestamp": datetime.utcnow().isoformat()}],
    )


def get_source_map(topic: str) -> list[dict]:
    collection = _collection("source_maps")
    try:
        results = collection.query(
            query_texts=[topic],
            n_results=1,
            where={"topic": topic},
        )
        if results["documents"][0]:
            return json.loads(results["documents"][0][0])
    except Exception:
        pass
    return []
