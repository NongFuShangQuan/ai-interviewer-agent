"""
RAG Vector Store - Hybrid implementation with embedding API + TF-IDF fallback.

Uses SiliconFlow embedding API when available, falls back to TF-IDF
keyword matching when embedding API is not available.
"""
import os
import json
import time
import math
import hashlib
import logging
import re
import numpy as np
import httpx
from typing import Optional
from collections import Counter
from app.core.config import get_settings

logger = logging.getLogger("rag.vectorstore")


# ===================== TF-IDF Engine =====================

class TFIDFEngine:
    """Lightweight TF-IDF engine for Chinese/English text matching"""
    
    def __init__(self):
        self.documents: list[str] = []
        self.idf: dict[str, float] = {}
        self.tfidf_matrix: list[dict[str, float]] = []
        self._fitted = False
    
    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer for Chinese and English"""
        text = text.lower()
        # Split Chinese characters individually, keep English words
        tokens = []
        # English words
        eng_words = re.findall(r'[a-zA-Z_]\w+', text)
        tokens.extend(eng_words)
        # Chinese characters (bigrams)
        chinese = re.findall(r'[\u4e00-\u9fff]', text)
        for i in range(len(chinese)):
            tokens.append(chinese[i])
            if i + 1 < len(chinese):
                tokens.append(chinese[i] + chinese[i+1])
        return tokens
    
    def fit(self, documents: list[str]):
        """Build TF-IDF index"""
        self.documents = documents
        n = len(documents)
        if n == 0:
            return
        
        # Tokenize all documents
        doc_tokens = [self._tokenize(doc) for doc in documents]
        
        # Calculate IDF
        df = Counter()
        for tokens in doc_tokens:
            unique = set(tokens)
            for t in unique:
                df[t] += 1
        
        self.idf = {}
        for term, freq in df.items():
            self.idf[term] = math.log((n + 1) / (freq + 1)) + 1
        
        # Calculate TF-IDF vectors
        self.tfidf_matrix = []
        for tokens in doc_tokens:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec = {}
            for term, count in tf.items():
                vec[term] = (count / total) * self.idf.get(term, 1.0)
            self.tfidf_matrix.append(vec)
        
        self._fitted = True
        logger.info(f"TF-IDF fitted: {n} documents, {len(self.idf)} terms")
    
    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """Search for similar documents, returns (index, score) pairs"""
        if not self._fitted or not self.documents:
            return []
        
        query_tokens = self._tokenize(query)
        query_tf = Counter(query_tokens)
        query_total = len(query_tokens) if query_tokens else 1
        
        query_vec = {}
        for term, count in query_tf.items():
            query_vec[term] = (count / query_total) * self.idf.get(term, 1.0)
        
        # Cosine similarity
        query_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1e-10
        
        scores = []
        for i, doc_vec in enumerate(self.tfidf_matrix):
            dot = 0
            for term, qval in query_vec.items():
                if term in doc_vec:
                    dot += qval * doc_vec[term]
            doc_norm = math.sqrt(sum(v * v for v in doc_vec.values())) or 1e-10
            similarity = dot / (query_norm * doc_norm)
            scores.append((i, similarity))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ===================== Embedding Client =====================

# ===================== Embedding Providers =====================

EMBEDDING_PROVIDERS = {
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "BAAI/bge-large-zh-v1.5",
        "dimension": 1024,
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "text-embedding-3-small",
        "dimension": 1536,
    },
    "mimo": {
        "name": "MiMo",
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "model": "text-embedding",
        "dimension": 1024,
    },
}


def detect_provider(base_url: str) -> str:
    """Auto-detect embedding provider from base URL"""
    if "siliconflow" in base_url:
        return "siliconflow"
    elif "openai" in base_url:
        return "openai"
    elif "mimo" in base_url or "xiaomimimo" in base_url:
        return "mimo"
    return "siliconflow"  # default


class EmbeddingClient:
    """Multi-provider Embedding API client with TF-IDF fallback"""
    
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_api_base_url
        self.provider = detect_provider(self.base_url)
        provider_info = EMBEDDING_PROVIDERS.get(self.provider, {})
        self.model = model or provider_info.get("model", "BAAI/bge-large-zh-v1.5")
        self._cache: dict[str, list[float]] = {}
        self._cache_file = "app/data/rag/embedding_cache.json"
        self._api_available: Optional[bool] = None  # Unknown yet
        self._load_cache()
    
    def _load_cache(self):
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached embeddings")
        except Exception:
            self._cache = {}
    
    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
        except Exception:
            pass
    
    def _text_hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    async def embed(self, text: str) -> list[float]:
        """Get embedding for a single text"""
        text_hash = self._text_hash(text)
        if text_hash in self._cache:
            return self._cache[text_hash]
        
        # Check if API is available
        if self._api_available is False:
            return self._fallback_embedding(text)
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": text}
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["data"][0]["embedding"]
                self._api_available = True
                self._cache[text_hash] = embedding
                if len(self._cache) % 10 == 0:
                    self._save_cache()
                return embedding
        except Exception as e:
            if self._api_available is None:
                logger.warning(f"Embedding API not available, using TF-IDF fallback: {e}")
                self._api_available = False
            return self._fallback_embedding(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts"""
        if self._api_available is False:
            return [self._fallback_embedding(t) for t in texts]
        
        results = []
        uncached = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            text_hash = self._text_hash(text)
            if text_hash in self._cache:
                results.append(self._cache[text_hash])
            else:
                results.append(None)
                uncached.append(text)
                uncached_indices.append(i)
        
        if uncached:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json={"model": self.model, "input": uncached}
                    )
                    response.raise_for_status()
                    data = response.json()
                    self._api_available = True
                    for j, item in enumerate(data["data"]):
                        idx = uncached_indices[j]
                        embedding = item["embedding"]
                        results[idx] = embedding
                        self._cache[self._text_hash(uncached[j])] = embedding
                    self._save_cache()
            except Exception as e:
                if self._api_available is None:
                    logger.warning(f"Batch embedding API not available, using TF-IDF fallback: {e}")
                    self._api_available = False
                for j, idx in enumerate(uncached_indices):
                    if results[idx] is None:
                        results[idx] = self._fallback_embedding(uncached[j])
        
        return results
    
    def _fallback_embedding(self, text: str) -> list[float]:
        """Generate a deterministic fallback embedding"""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.RandomState(int.from_bytes(h[:4], "big"))
        vec = rng.randn(128).astype(float)
        vec = vec / (np.linalg.norm(vec) + 1e-10)
        return vec.tolist()
    
    @property
    def is_api_available(self) -> bool:
        return self._api_available is True


# ===================== Vector Store =====================

class SimpleVectorStore:
    """Hybrid vector store: embedding API + TF-IDF fallback"""
    
    def __init__(self, name: str, embedding_client: EmbeddingClient):
        self.name = name
        self.embedding_client = embedding_client
        self.documents: list[dict] = []
        self.vectors: Optional[np.ndarray] = None
        self.tfidf = TFIDFEngine()
        self.metadata: dict = {"name": name, "created_at": time.time(), "count": 0}
        self._persist_file = f"app/data/rag/{name}_store.json"
    
    async def add_documents(self, documents: list[dict], text_field: str = "text"):
        """Add documents with their embeddings"""
        texts = [doc.get(text_field, "") for doc in documents]
        embeddings = await self.embedding_client.embed_batch(texts)
        
        for doc, emb in zip(documents, embeddings):
            self.documents.append(doc)
        
        vectors = np.array(embeddings, dtype=np.float32)
        if self.vectors is not None:
            self.vectors = np.vstack([self.vectors, vectors])
        else:
            self.vectors = vectors
        
        # Also fit TF-IDF
        all_texts = [d.get(text_field, "") for d in self.documents]
        self.tfidf.fit(all_texts)
        
        self.metadata["count"] = len(self.documents)
        logger.info(f"VectorStore '{self.name}': added {len(documents)} docs, total {len(self.documents)}")
    
    async def search(self, query: str, top_k: int = 5, threshold: float = 0.0) -> list[dict]:
        """Search using embeddings if available, otherwise TF-IDF"""
        if not self.documents:
            return []
        
        if self.embedding_client.is_api_available and self.vectors is not None:
            return await self._search_vector(query, top_k, threshold)
        else:
            return self._search_tfidf(query, top_k, threshold)
    
    async def _search_vector(self, query: str, top_k: int, threshold: float) -> list[dict]:
        """Vector-based search"""
        query_vec = np.array(await self.embedding_client.embed(query), dtype=np.float32)
        norms = np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(query_vec)
        norms = np.where(norms == 0, 1e-10, norms)
        similarities = np.dot(self.vectors, query_vec) / norms
        
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= threshold:
                result = {**self.documents[idx], "_score": score}
                results.append(result)
        return results
    
    def _search_tfidf(self, query: str, top_k: int, threshold: float) -> list[dict]:
        """TF-IDF keyword-based search (fallback)"""
        tfidf_results = self.tfidf.search(query, top_k=top_k)
        results = []
        for idx, score in tfidf_results:
            if score >= threshold:
                result = {**self.documents[idx], "_score": score}
                results.append(result)
        return results
    
    async def persist(self):
        """Save store to disk"""
        try:
            os.makedirs(os.path.dirname(self._persist_file), exist_ok=True)
            data = {
                "metadata": self.metadata,
                "documents": self.documents,
                "vectors": self.vectors.tolist() if self.vectors is not None else None
            }
            with open(self._persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info(f"VectorStore '{self.name}': persisted {len(self.documents)} docs")
        except Exception as e:
            logger.error(f"Persist error: {e}")
    
    async def load(self) -> bool:
        """Load store from disk"""
        try:
            if not os.path.exists(self._persist_file):
                return False
            with open(self._persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.metadata = data.get("metadata", {})
            self.documents = data.get("documents", [])
            vectors = data.get("vectors")
            if vectors:
                self.vectors = np.array(vectors, dtype=np.float32)
            
            # Rebuild TF-IDF index
            if self.documents:
                texts = [d.get("text", "") for d in self.documents]
                self.tfidf.fit(texts)
            
            logger.info(f"VectorStore '{self.name}': loaded {len(self.documents)} docs")
            return True
        except Exception as e:
            logger.error(f"Load error: {e}")
            return False
    
    @property
    def count(self) -> int:
        return len(self.documents)