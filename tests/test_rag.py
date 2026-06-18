# -*- coding: utf-8 -*-
import unittest, sys, json, os
sys.path.insert(0, ".")
from app.rag.vectorstore import TFIDFEngine, EmbeddingClient


class TestTFIDFEngine(unittest.TestCase):
    def test_tokenize_returns_list(self):
        tokens = TFIDFEngine()._tokenize("Python并发编程")
        self.assertIsInstance(tokens, list)
        self.assertTrue(len(tokens) > 0)

    def test_tokenize_english(self):
        tokens = TFIDFEngine()._tokenize("async programming")
        self.assertIn("async", tokens)
        self.assertIn("programming", tokens)

    def test_fit_and_search(self):
        engine = TFIDFEngine()
        engine.fit(["Python GIL", "Java GC", "JavaScript async", "Python asyncio"])
        self.assertTrue(engine._fitted)
        results = engine.search("Python", top_k=2)
        self.assertTrue(len(results) > 0)

    def test_search_ranking(self):
        engine = TFIDFEngine()
        engine.fit(["Python threading", "Java concurrency", "Go goroutines"])
        results = engine.search("Python", top_k=3)
        self.assertTrue(results[0][0] == 0)  # Python doc should rank first

    def test_search_empty(self):
        self.assertEqual(TFIDFEngine().search("test"), [])

    def test_bigrams(self):
        tokens = TFIDFEngine()._tokenize("面试")
        self.assertTrue(len(tokens) >= 2)


class TestEmbeddingClient(unittest.TestCase):
    def test_fallback_deterministic(self):
        c = EmbeddingClient(api_key="fake", base_url="http://fake")
        c._api_available = False
        self.assertEqual(c._fallback_embedding("test"), c._fallback_embedding("test"))

    def test_fallback_normalized(self):
        import numpy as np
        c = EmbeddingClient(api_key="fake", base_url="http://fake")
        c._api_available = False
        emb = c._fallback_embedding("text")
        self.assertAlmostEqual(np.linalg.norm(emb), 1.0, places=2)

    def test_hash(self):
        c = EmbeddingClient(api_key="fake", base_url="http://fake")
        self.assertEqual(c._text_hash("hello"), c._text_hash("hello"))
        self.assertNotEqual(c._text_hash("hello"), c._text_hash("world"))


class TestQuestionBank(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(os.path.exists("app/data/rag/question_bank.json"))

    def test_structure(self):
        with open("app/data/rag/question_bank.json", encoding="utf-8") as f:
            bank = json.load(f)
        self.assertIn("metadata", bank)
        self.assertTrue(bank["metadata"]["total_questions"] > 0)

    def test_families(self):
        with open("app/data/rag/question_bank.json", encoding="utf-8") as f:
            bank = json.load(f)
        self.assertTrue(len(bank["metadata"]["job_families"]) >= 10)


if __name__ == "__main__":
    unittest.main()