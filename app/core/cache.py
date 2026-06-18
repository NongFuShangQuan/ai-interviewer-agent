"""LLM Response Cache - Reduces redundant LLM calls for speed and stability.

Features:
- LRU eviction with configurable max size
- TTL-based expiration (default 1 hour)
- Async-safe (works with asyncio)
- Persistent to disk (survives restarts)
- Cache key based on (agent_name, prompt_hash) for deterministic hits
"""
import hashlib
import json
import time
import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger("core.cache")

CACHE_DIR = Path("E:/PythonProject/AIInterview/data/cache")
DEFAULT_MAX_SIZE = 500
DEFAULT_TTL = 3600  # 1 hour


class LLMCache:
    """Thread-safe LRU cache with TTL and disk persistence."""

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def _make_key(self, agent_name: str, prompt_text: str, **extra) -> str:
        """Generate deterministic cache key."""
        raw = f"{agent_name}:{prompt_text}"
        for k in sorted(extra.keys()):
            raw += f":{k}={extra[k]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def get(self, agent_name: str, prompt_text: str, **extra) -> Optional[Any]:
        """Get cached response. Returns None on miss."""
        key = self._make_key(agent_name, prompt_text, **extra)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.debug(f"Cache HIT for {agent_name} (key={key[:8]})")
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    async def put(self, agent_name: str, prompt_text: str, value: Any, **extra):
        """Store response in cache."""
        key = self._make_key(agent_name, prompt_text, **extra)
        async with self._lock:
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
            # LRU eviction
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
        # Persist periodically (every 10 writes)
        if len(self._cache) % 10 == 0:
            self._save_to_disk()

    def _load_from_disk(self):
        """Load cache from disk file."""
        cache_file = CACHE_DIR / "llm_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                for key, (value, ts) in data.items():
                    if now - ts < self._ttl:
                        self._cache[key] = (value, ts)
                logger.info(f"Loaded {len(self._cache)} cached entries from disk")
            except Exception as e:
                logger.warning(f"Failed to load cache from disk: {e}")

    def _save_to_disk(self):
        """Persist cache to disk."""
        cache_file = CACHE_DIR / "llm_cache.json"
        try:
            data = dict(self._cache)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save cache to disk: {e}")

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
            "ttl": self._ttl,
        }

    def shutdown(self):
        """Save cache to disk on shutdown."""
        self._save_to_disk()
        logger.info(f"Cache saved: {len(self._cache)} entries")


# Global singleton
_cache_instance: Optional[LLMCache] = None


def get_cache() -> LLMCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = LLMCache()
    return _cache_instance