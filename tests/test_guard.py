# -*- coding: utf-8 -*-
"""Tests for Guard system"""
import unittest
import time
import sys
sys.path.insert(0, ".")
from app.agents.guard import (
    GuardConfig, CallResult, ToolCallRecord, LoopEvent,
    LoopDetector, IterationLimiter, RapidFireDetector,
    DegradationEngine, ToolCallGuard
)


class TestGuardConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = GuardConfig()
        self.assertEqual(cfg.MAX_ITERATIONS_PER_TURN, 5)
        self.assertEqual(cfg.MAX_TOTAL_ITERATIONS, 100)
        self.assertTrue(cfg.ENABLE_DEGRADATION)


class TestCallResult(unittest.TestCase):
    def test_values(self):
        self.assertEqual(CallResult.SUCCESS.value, "success")
        self.assertEqual(CallResult.ERROR.value, "error")
        self.assertEqual(CallResult.DEGRADED.value, "degraded")


class TestToolCallRecord(unittest.TestCase):
    def _make(self, **kw):
        d = dict(timestamp=time.time(), agent_name="interviewer",
                 tool_name="gen_q", params_hash="abc", params_summary="r=1",
                 result=CallResult.SUCCESS, duration_ms=100.0,
                 iteration=1, turn_num=1, interview_id="t1")
        d.update(kw)
        return ToolCallRecord(**d)

    def test_creation(self):
        self.assertEqual(self._make().agent_name, "interviewer")

    def test_fingerprint(self):
        self.assertEqual(len(self._make().fingerprint()), 12)

    def test_same_fingerprint(self):
        self.assertEqual(self._make().fingerprint(), self._make().fingerprint())

    def test_different_fingerprint(self):
        self.assertNotEqual(self._make(agent_name="a").fingerprint(),
                           self._make(agent_name="b").fingerprint())

    def test_to_dict(self):
        d = self._make().to_dict()
        self.assertIn("agent", d)
        self.assertIn("fingerprint", d)


class TestIterationLimiter(unittest.TestCase):
    def _make(self, per_turn=5, total=100):
        cfg = GuardConfig()
        cfg.MAX_ITERATIONS_PER_TURN = per_turn
        cfg.MAX_TOTAL_ITERATIONS = total
        return IterationLimiter(cfg)

    def test_within_limit(self):
        result = self._make(per_turn=5).check_and_increment("interviewer")
        self.assertTrue(result[0])

    def test_exceeds_per_turn(self):
        l = self._make(per_turn=3)
        for _ in range(3):
            l.check_and_increment("interviewer")
        ok, msg = l.check_and_increment("interviewer")
        self.assertFalse(ok)
        self.assertIn("exceeded", msg)

    def test_new_turn_resets(self):
        l = self._make(per_turn=2)
        l.check_and_increment("interviewer")
        l.check_and_increment("interviewer")
        ok, _ = l.check_and_increment("interviewer")
        self.assertFalse(ok)
        l.new_turn()
        ok, _ = l.check_and_increment("interviewer")
        self.assertTrue(ok)


class TestRapidFireDetector(unittest.TestCase):
    def _make_det(self, max_calls=6):
        cfg = GuardConfig()
        cfg.MAX_CALLS_IN_RAPID_WINDOW = max_calls
        return RapidFireDetector(cfg)

    def _make_rec(self):
        return ToolCallRecord(time.time(), "a", "t", "", "", CallResult.SUCCESS, 0, 1, 1, "id")

    def test_normal_rate(self):
        d = self._make_det(max_calls=10)
        for _ in range(5):
            self.assertFalse(d.check(self._make_rec()))

    def test_rapid_fire(self):
        d = self._make_det(max_calls=3)
        for _ in range(3):
            d.check(self._make_rec())
        self.assertTrue(d.check(self._make_rec()))


class TestDegradationEngine(unittest.TestCase):
    def test_get_fallback(self):
        fallback, strategy = DegradationEngine().get_fallback("generate_question")
        self.assertIsNotNone(fallback)

    def test_fallbacks_registered(self):
        self.assertTrue(len(DegradationEngine().FALLBACKS) > 0)


if __name__ == "__main__":
    unittest.main()