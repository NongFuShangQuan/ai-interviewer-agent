# -*- coding: utf-8 -*-
import unittest, sys
sys.path.insert(0, ".")
from app.agents.evaluator import extract_json_from_text


class TestExtractJson(unittest.TestCase):
    def test_direct_json(self):
        result = extract_json_from_text('{"score": 8.5}')
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 8.5)

    def test_json_in_markdown(self):
        text = 'Result:\n```json\n{"score": 7.0}\n```'
        result = extract_json_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 7.0)

    def test_json_with_text(self):
        text = 'Here: {"score": 9.0} done.'
        result = extract_json_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 9.0)

    def test_empty(self):
        self.assertIsNone(extract_json_from_text(""))
        self.assertIsNone(extract_json_from_text(None))

    def test_no_json(self):
        self.assertIsNone(extract_json_from_text("plain text"))

    def test_invalid_json(self):
        self.assertIsNone(extract_json_from_text('{"score": 8.5'))

    def test_full_evaluation(self):
        text = '{"overall_score": 7.5, "technical_score": 8.0, "recommendation": "hire"}'
        result = extract_json_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_score"], 7.5)
        self.assertEqual(result["recommendation"], "hire")


if __name__ == "__main__":
    unittest.main()