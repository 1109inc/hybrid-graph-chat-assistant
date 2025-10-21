# emb_cache.py
import sqlite3
import hashlib
import json
import time
import numpy as np
from typing import List, Optional, Tuple

DB_PATH = "embeddings_cache.sqlite"
MAX_ENTRIES = 200_000      # safety cap - adjust as needed
TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

def _make_key(text: str, model: str) -> str:
    # Normalize whitespace and lowercase for stable keys
    cleaned = " ".join(text.split())
    base = f"{model}|{cleaned}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def _ensure_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS embeddings (
        key TEXT PRIMARY KEY,
        model TEXT,
        text TEXT,
        emb BLOB,
        created_at REAL
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON embeddings(created_at)")
    conn.commit()
    return conn

def _serialize_emb(emb: List[float]) -> bytes:
    arr = np.array(emb, dtype=np.float32)
    return arr.tobytes()

def _deserialize_emb(b: bytes) -> List[float]:
    arr = np.frombuffer(b, dtype=np.float32)
    return arr.tolist()

def get_embedding_from_cache(text: str, model: str) -> Optional[List[float]]:
    key = _make_key(text, model)
    conn = _ensure_db()
    cur = conn.cursor()
    cur.execute("SELECT emb, created_at FROM embeddings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    emb_blob, created_at = row
    # Optionally expire entries older than TTL
    if TTL_SECONDS and (time.time() - created_at) > TTL_SECONDS:
        try:
            conn = _ensure_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM embeddings WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return None
    return _deserialize_emb(emb_blob)

def put_embedding_in_cache(text: str, model: str, emb: List[float]) -> None:
    key = _make_key(text, model)
    conn = _ensure_db()
    cur = conn.cursor()
    emb_blob = _serialize_emb(emb)
    cur.execute(
        "INSERT OR REPLACE INTO embeddings (key, model, text, emb, created_at) VALUES (?, ?, ?, ?, ?)",
        (key, model, text[:2000], emb_blob, time.time())
    )
    conn.commit()
    # simple eviction: if DB too large, delete oldest rows
    cur.execute("SELECT COUNT(1) FROM embeddings")
    count = cur.fetchone()[0]
    if count > MAX_ENTRIES:
        # delete oldest 10% entries
        cutoff = int(MAX_ENTRIES * 0.9)
        cur.execute("""
            DELETE FROM embeddings
            WHERE key IN (
                SELECT key FROM embeddings ORDER BY created_at ASC LIMIT ?
            )
        """, (count - cutoff,))
        conn.commit()
    conn.close()

def batch_get_embeddings(texts: List[str], model: str) -> Tuple[dict, List[int]]:
    """
    Return a dict mapping index -> emb for found items, and a list of missing indices.
    """
    if not texts:
        return {}, []

    conn = _ensure_db()
    cur = conn.cursor()
    keys = [_make_key(t, model) for t in texts]

    # build mapping key -> indices for O(n) lookup
    key_to_idxs = {}
    for i, k in enumerate(keys):
        key_to_idxs.setdefault(k, []).append(i)

    found = {}
    now = time.time()
    expired_keys = set()

    # SQLite limits bound variables (~999 by default) -> chunk keys
    MAX_VARS = 900
    for i in range(0, len(keys), MAX_VARS):
        chunk = keys[i:i+MAX_VARS]
        placeholders = ",".join("?" for _ in chunk)
        query = f"SELECT key, emb, created_at FROM embeddings WHERE key IN ({placeholders})"
        cur.execute(query, chunk)
        rows = cur.fetchall()
        for key, emb_blob, created_at in rows:
            if TTL_SECONDS and (now - created_at) > TTL_SECONDS:
                expired_keys.add(key)
                continue
            emb = _deserialize_emb(emb_blob)
            for idx in key_to_idxs.get(key, []):
                found[idx] = emb

    # missing indices
    missing = [i for i in range(len(texts)) if i not in found]

    # delete expired keys if any
    if expired_keys:
        placeholders = ",".join("?" for _ in expired_keys)
        cur.execute(f"DELETE FROM embeddings WHERE key IN ({placeholders})", tuple(expired_keys))
        conn.commit()

    conn.close()
    return found, missing
