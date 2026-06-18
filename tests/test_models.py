# -*- coding: utf-8 -*-
import unittest, sys, json
sys.path.insert(0, ".")
from app.models.models import Candidate, Interview, Message, Evaluation, InterviewStatus


class TestInterviewStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(InterviewStatus.PENDING.value, "pending")
        self.assertEqual(InterviewStatus.COMPLETED.value, "completed")


class TestModels(unittest.TestCase):
    def test_candidate_cols(self):
        cols = [c.name for c in Candidate.__table__.columns]
        self.assertIn("name", cols)
        self.assertIn("email", cols)

    def test_interview_cols(self):
        cols = [c.name for c in Interview.__table__.columns]
        self.assertIn("token", cols)
        self.assertIn("job_title", cols)

    def test_evaluation_cols(self):
        cols = [c.name for c in Evaluation.__table__.columns]
        self.assertIn("overall_score", cols)
        self.assertIn("recommendation", cols)


class TestJobTemplates(unittest.TestCase):
    def test_exist(self):
        with open("app/data/job_templates.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("categories", data)
        self.assertTrue(len(data["categories"]) >= 5)

    def test_job_structure(self):
        with open("app/data/job_templates.json", encoding="utf-8") as f:
            data = json.load(f)
        for cat in data["categories"][:2]:
            self.assertIn("name", cat)
            for job in cat["jobs"][:1]:
                self.assertIn("title", job)
                self.assertIn("description", job)


if __name__ == "__main__":
    unittest.main()