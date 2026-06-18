# -*- coding: utf-8 -*-
import unittest, sys
sys.path.insert(0, ".")
from app.agents.state import InterviewState, EvaluationResult, InterviewRound


class TestInterviewState(unittest.TestCase):
    def test_has_annotations(self):
        self.assertTrue(hasattr(InterviewState, '__annotations__'))

    def test_has_required_fields(self):
        fields = InterviewState.__annotations__
        for f in ["interview_id", "candidate_name", "job_title", "current_round", "total_rounds"]:
            self.assertIn(f, fields)

    def test_has_messages(self):
        self.assertIn("messages", InterviewState.__annotations__)

    def test_has_rounds_data(self):
        self.assertIn("rounds_data", InterviewState.__annotations__)


class TestEvaluationResult(unittest.TestCase):
    def test_has_score_fields(self):
        fields = EvaluationResult.__annotations__
        for f in ["overall_score", "technical_score", "communication_score"]:
            self.assertIn(f, fields)


class TestInterviewRound(unittest.TestCase):
    def test_creation(self):
        r = InterviewRound(round_num=1, question="Hello?")
        self.assertEqual(r.round_num, 1)
        self.assertEqual(r.answer, "")


if __name__ == "__main__":
    unittest.main()