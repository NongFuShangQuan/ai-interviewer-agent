"""
Tool Call Guard - Protection against infinite loops and anomalous tool calls.

Architecture:
    ToolCallGuard
    ├── CallTracker        - Records every tool call with timestamp, fingerprint, result
    ├── LoopDetector       - Fingerprint-based pattern detection in sliding window
    ├── IterationLimiter   - Per-agent max iteration enforcement
    ├── DegradationEngine  - Fallback strategies when anomalies detected
    └── BackflowLogger     - Structured logging for SFT/RL negative samples

Flow:
    tool_call -> guard.check() -> [PASS] -> execute
                                 -> [BLOCKED] -> degrade + log + optional escalation
"""

import hashlib
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Any
from collections import deque
from enum import Enum
import logging

logger = logging.getLogger("agent.guard")


# ===================== Configuration =====================

class GuardConfig:
    """Guard configuration - all thresholds are tunable"""
    # Max iterations per agent per interview turn
    MAX_ITERATIONS_PER_TURN = 5
    # Max total iterations per interview (all agents combined)
    MAX_TOTAL_ITERATIONS = 100
    # Sliding window size for loop detection
    LOOP_WINDOW_SIZE = 8
    # Minimum repeated pattern length to detect as loop
    MIN_LOOP_PATTERN_LEN = 2
    # Max identical calls within window (same fingerprint)
    MAX_SAME_CALL_IN_WINDOW = 3
    # Time window for rapid-fire detection (seconds)
    RAPID_FIRE_WINDOW = 5.0
    # Max calls within rapid-fire window
    MAX_CALLS_IN_RAPID_WINDOW = 6
    # Cooldown after loop detected (seconds)
    COOLDOWN_AFTER_LOOP = 30.0
    # Enable degradation (fallback to rule-based)
    ENABLE_DEGRADATION = True
    # Enable escalation (notify human)
    ENABLE_ESCALATION = True
    # Max consecutive degradations before hard stop
    MAX_CONSECUTIVE_DEGRADATIONS = 3


# ===================== Data Structures =====================

class CallResult(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"  # used fallback instead of real tool
    BLOCKED = "blocked"    # guard blocked the call


@dataclass
class ToolCallRecord:
    """A single tool call record"""
    timestamp: float
    agent_name: str
    tool_name: str
    params_hash: str       # hash of parameters
    params_summary: str    # human-readable summary (truncated)
    result: CallResult
    duration_ms: float
    iteration: int
    turn_num: int
    interview_id: str
    error_msg: str = ""

    def fingerprint(self) -> str:
        """Generate fingerprint for this call (agent + tool + params)"""
        return hashlib.md5(
            f"{self.agent_name}:{self.tool_name}:{self.params_hash}".encode()
        ).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "agent": self.agent_name,
            "tool": self.tool_name,
            "params_hash": self.params_hash,
            "params_summary": self.params_summary,
            "result": self.result.value,
            "duration_ms": self.duration_ms,
            "iteration": self.iteration,
            "turn": self.turn_num,
            "interview_id": self.interview_id,
            "error": self.error_msg,
            "fingerprint": self.fingerprint(),
        }


@dataclass
class LoopEvent:
    """A detected loop event - serves as negative sample for training"""
    timestamp: float
    interview_id: str
    loop_type: str         # "exact_repeat", "pattern_repeat", "rapid_fire", "max_iterations"
    pattern: list          # list of fingerprints in the loop
    call_records: list     # full ToolCallRecords involved
    action_taken: str      # "degraded", "escalated", "stopped"
    resolution: str        # what fallback was used

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "interview_id": self.interview_id,
            "loop_type": self.loop_type,
            "pattern": self.pattern,
            "action": self.action_taken,
            "resolution": self.resolution,
            "calls_involved": len(self.call_records),
            "call_details": [c.to_dict() for c in self.call_records],
        }

    def to_negative_sample(self) -> dict:
        """Convert to structured negative sample for SFT/RL training"""
        return {
            "type": "tool_loop_negative_sample",
            "event": self.to_dict(),
            "label": "REJECT",
            "instruction": (
                f"Agent {self.call_records[0].agent_name if self.call_records else 'unknown'} "
                f"entered a {self.loop_type} loop calling tool "
                f"{self.call_records[0].tool_name if self.call_records else 'unknown'}"
            ),
            "context": {
                "tool_sequence": [c.tool_name for c in self.call_records],
                "param_hashes": [c.params_hash for c in self.call_records],
                "durations": [c.duration_ms for c in self.call_records],
            },
            "rejection_reason": f"Loop detected: {self.loop_type}, pattern length={len(self.pattern)}",
            "suggested_fix": "Add parameter variation or early termination condition",
        }


# ===================== Loop Detector =====================

class LoopDetector:
    """Detects repeating patterns in tool call sequences using fingerprinting"""

    def __init__(self, config: GuardConfig):
        self.config = config
        self.window: deque = deque(maxlen=config.LOOP_WINDOW_SIZE)

    def add_call(self, record: ToolCallRecord) -> LoopEvent | None:
        """Add a call to the window and check for loops. Returns LoopEvent if detected."""
        fp = record.fingerprint()
        self.window.append(fp)

        # Check 1: Exact repeat - same fingerprint appearing too many times
        count = sum(1 for f in self.window if f == fp)
        if count >= self.config.MAX_SAME_CALL_IN_WINDOW:
            return LoopEvent(
                timestamp=time.time(),
                interview_id=record.interview_id,
                loop_type="exact_repeat",
                pattern=[fp],
                call_records=[record],
                action_taken="",
                resolution="",
            )

        # Check 2: Repeating pattern (e.g., A-B-A-B or A-B-C-A-B-C)
        pattern = self._find_repeating_pattern()
        if pattern:
            return LoopEvent(
                timestamp=time.time(),
                interview_id=record.interview_id,
                loop_type="pattern_repeat",
                pattern=pattern,
                call_records=[record],
                action_taken="",
                resolution="",
            )

        return None

    def _find_repeating_pattern(self) -> list | None:
        """Find a repeating pattern in the current window"""
        window = list(self.window)
        n = len(window)
        if n < 4:  # need at least 4 to detect a pattern of length 2
            return None

        # Try pattern lengths from 2 to n/2
        for plen in range(self.config.MIN_LOOP_PATTERN_LEN, n // 2 + 1):
            pattern = window[-plen:]
            # Check if this pattern repeats at least twice consecutively
            matches = 0
            for i in range(n - plen, -1, -plen):
                if i - plen < 0:
                    break
                segment = window[i - plen:i]
                if segment == pattern:
                    matches += 1
                else:
                    break
            if matches >= 2:  # pattern repeated at least 2 more times
                return pattern

        return None

    def reset(self):
        self.window.clear()


# ===================== Iteration Limiter =====================

class IterationLimiter:
    """Enforces per-agent and total iteration limits"""

    def __init__(self, config: GuardConfig):
        self.config = config
        self.agent_counts: dict[str, int] = {}
        self.total_count: int = 0
        self.turn_count: int = 0

    def check_and_increment(self, agent_name: str) -> tuple[bool, str]:
        """
        Check if the call is within limits. Returns (allowed, reason).
        Increments counters if allowed.
        """
        self.total_count += 1
        self.agent_counts[agent_name] = self.agent_counts.get(agent_name, 0) + 1

        # Check per-agent limit
        agent_count = self.agent_counts[agent_name]
        if agent_count > self.config.MAX_ITERATIONS_PER_TURN:
            return False, (
                f"Agent '{agent_name}' exceeded max iterations per turn "
                f"({agent_count}/{self.config.MAX_ITERATIONS_PER_TURN})"
            )

        # Check total limit
        if self.total_count > self.config.MAX_TOTAL_ITERATIONS:
            return False, (
                f"Total iterations exceeded max limit "
                f"({self.total_count}/{self.config.MAX_TOTAL_ITERATIONS})"
            )

        return True, ""

    def new_turn(self):
        """Reset per-agent counters for a new interview turn"""
        self.agent_counts.clear()
        self.turn_count += 1

    def reset(self):
        self.agent_counts.clear()
        self.total_count = 0
        self.turn_count = 0


# ===================== Rapid Fire Detector =====================

class RapidFireDetector:
    """Detects abnormally rapid tool calls (potential runaway loop)"""

    def __init__(self, config: GuardConfig):
        self.config = config
        self.recent_calls: deque = deque()

    def check(self, record: ToolCallRecord) -> bool:
        """Returns True if rapid fire detected"""
        now = record.timestamp
        self.recent_calls.append(now)

        # Remove old entries outside the window
        cutoff = now - self.config.RAPID_FIRE_WINDOW
        while self.recent_calls and self.recent_calls[0] < cutoff:
            self.recent_calls.popleft()

        return len(self.recent_calls) > self.config.MAX_CALLS_IN_RAPID_WINDOW

    def reset(self):
        self.recent_calls.clear()


# ===================== Degradation Engine =====================

class DegradationEngine:
    """Provides fallback responses when loops are detected"""

    # Pre-defined fallback responses by tool type
    FALLBACKS = {
        "generate_question": {
            "fallback": "请简单介绍一下您自己，以及您对这个职位的理解。",
            "strategy": "use_cached_question",
        },
        "evaluate_round": {
            "fallback": {"round_score": 5.0, "evaluation_notes": "系统评估异常，使用默认分数"},
            "strategy": "use_default_score",
        },
        "final_evaluation": {
            "fallback": {
                "overall_score": 5.0,
                "technical_score": 5.0,
                "communication_score": 5.0,
                "problem_solving_score": 5.0,
                "cultural_fit_score": 5.0,
                "experience_score": 5.0,
                "summary": "评估系统异常，无法生成详细报告。请人工复核面试记录。",
                "strengths": "需要人工评估",
                "weaknesses": "需要人工评估",
                "recommendation": "maybe",
                "detailed_feedback": "系统检测到异常循环，已降级为人工评估模式。",
            },
            "strategy": "use_default_evaluation",
        },
    }

    def get_fallback(self, tool_name: str) -> tuple[Any, str]:
        """Get fallback response for a tool. Returns (result, strategy)."""
        fb = self.FALLBACKS.get(tool_name)
        if fb:
            return fb["fallback"], fb["strategy"]
        # Generic fallback
        return None, "return_none"


# ===================== Main Guard =====================

class ToolCallGuard:
    """
    Main guard class - orchestrates all protection mechanisms.

    Usage:
        guard = ToolCallGuard(interview_id="xxx")

        # Before calling a tool:
        result = await guard.check_and_execute(
            agent_name="evaluator",
            tool_name="evaluate_round",
            params={"question": "...", "answer": "..."},
            real_executor=my_real_function,
        )

        if result.degraded:
            # Used fallback
            pass
    """

    def __init__(self, interview_id: str, config: GuardConfig | None = None):
        self.config = config or GuardConfig()
        self.interview_id = interview_id
        self.call_records: list[ToolCallRecord] = []
        self.loop_events: list[LoopEvent] = []
        self.consecutive_degradations: int = 0
        self.is_halted: bool = False
        self.halt_reason: str = ""

        # Sub-components
        self.loop_detector = LoopDetector(self.config)
        self.iteration_limiter = IterationLimiter(self.config)
        self.rapid_fire_detector = RapidFireDetector(self.config)
        self.degradation_engine = DegradationEngine()

        # Lock for thread safety
        self._lock = threading.RLock()

        # Escalation callback (set externally)
        self.on_escalation: Callable | None = None
        # Backflow callback (set externally, for logging to training data)
        self.on_backflow: Callable | None = None

    def new_turn(self):
        """Call at the start of each interview turn"""
        with self._lock:
            self.iteration_limiter.new_turn()
            self.consecutive_degradations = 0

    def _params_hash(self, params: dict) -> str:
        """Generate a stable hash of parameters"""
        try:
            # Sort keys for stability, truncate large values
            stable = json.dumps(params, sort_keys=True, default=str)[:500]
        except Exception:
            stable = str(params)[:500]
        return hashlib.md5(stable.encode()).hexdigest()[:10]

    def _params_summary(self, params: dict) -> str:
        """Generate a human-readable summary of parameters"""
        parts = []
        for k, v in params.items():
            val_str = str(v)[:60]
            parts.append(f"{k}={val_str}")
        return ", ".join(parts)[:200]

    async def check_and_execute(
        self,
        agent_name: str,
        tool_name: str,
        params: dict,
        real_executor: Callable,
    ) -> tuple[Any, CallResult]:
        """
        Main entry point: check guard conditions, then execute or degrade.

        Returns: (result, CallResult)
        """
        with self._lock:
            # Hard stop if previously halted
            if self.is_halted:
                fallback, strategy = self.degradation_engine.get_fallback(tool_name)
                return fallback, CallResult.BLOCKED

            # Check iteration limits
            allowed, reason = self.iteration_limiter.check_and_increment(agent_name)
            if not allowed:
                event = self._create_loop_event(
                    "max_iterations", [], reason
                )
                self._handle_loop(event, tool_name)
                fallback, strategy = self.degradation_engine.get_fallback(tool_name)
                return fallback, CallResult.DEGRADED

        # Create the call record (before execution)
        params_hash = self._params_hash(params)
        record = ToolCallRecord(
            timestamp=time.time(),
            agent_name=agent_name,
            tool_name=tool_name,
            params_hash=params_hash,
            params_summary=self._params_summary(params),
            result=CallResult.SUCCESS,
            duration_ms=0,
            iteration=self.iteration_limiter.total_count,
            turn_num=self.iteration_limiter.turn_count,
            interview_id=self.interview_id,
        )

        # Check loop detection BEFORE execution
        with self._lock:
            loop_event = self.loop_detector.add_call(record)
            if loop_event:
                loop_event.call_records = self._get_matching_records(
                    record.fingerprint()
                )
                self._handle_loop(loop_event, tool_name)
                fallback, strategy = self.degradation_engine.get_fallback(tool_name)
                record.result = CallResult.DEGRADED
                self.call_records.append(record)
                return fallback, CallResult.DEGRADED

            # Check rapid fire
            if self.rapid_fire_detector.check(record):
                event = self._create_loop_event(
                    "rapid_fire", [record], "Too many calls in short time"
                )
                self._handle_loop(event, tool_name)
                fallback, strategy = self.degradation_engine.get_fallback(tool_name)
                record.result = CallResult.DEGRADED
                self.call_records.append(record)
                return fallback, CallResult.DEGRADED

        # Execute the real tool
        start_time = time.time()
        try:
            result = await real_executor(**params)
            duration = (time.time() - start_time) * 1000

            record.result = CallResult.SUCCESS
            record.duration_ms = duration
            with self._lock:
                self.call_records.append(record)
                self.consecutive_degradations = 0

            return result, CallResult.SUCCESS

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            record.result = CallResult.ERROR
            record.duration_ms = duration
            record.error_msg = str(e)[:200]

            with self._lock:
                self.call_records.append(record)

            # On error, use fallback
            fallback, strategy = self.degradation_engine.get_fallback(tool_name)
            logger.warning(
                f"Tool call error: {agent_name}.{tool_name}: {e}, using fallback"
            )
            return fallback, CallResult.ERROR

    def _get_matching_records(self, fingerprint: str) -> list:
        """Get recent records matching a fingerprint"""
        return [r for r in self.call_records[-20:] if r.fingerprint() == fingerprint]

    def _create_loop_event(
        self, loop_type: str, records: list, reason: str
    ) -> LoopEvent:
        return LoopEvent(
            timestamp=time.time(),
            interview_id=self.interview_id,
            loop_type=loop_type,
            pattern=[r.fingerprint() for r in records] if records else [],
            call_records=records,
            action_taken="",
            resolution=reason,
        )

    def _handle_loop(self, event: LoopEvent, tool_name: str):
        """Handle a detected loop event - called while holding self._lock"""
        self.consecutive_degradations += 1

        # Decide action
        if self.consecutive_degradations >= self.config.MAX_CONSECUTIVE_DEGRADATIONS:
            event.action_taken = "halted"
            event.resolution = "Max consecutive degradations reached, halting guard"
            self.is_halted = True
            self.halt_reason = event.resolution
        elif self.config.ENABLE_DEGRADATION:
            event.action_taken = "degraded"
            _, event.resolution = self.degradation_engine.get_fallback(tool_name)
        else:
            event.action_taken = "logged_only"

        self.loop_events.append(event)

        # Log the event
        logger.warning(
            f"[GUARD] Loop detected in interview {self.interview_id}: "
            f"type={event.loop_type}, action={event.action_taken}, "
            f"pattern={event.pattern}"
        )

        # Backflow: emit negative sample for training data
        if self.on_backflow:
            try:
                self.on_backflow(event.to_negative_sample())
            except Exception as e:
                logger.error(f"Backflow callback error: {e}")

        # Escalation: notify human if needed
        if self.config.ENABLE_ESCALATION and event.action_taken == "halted":
            if self.on_escalation:
                try:
                    self.on_escalation(event)
                except Exception as e:
                    logger.error(f"Escalation callback error: {e}")

    def get_status(self) -> dict:
        """Get current guard status for monitoring"""
        with self._lock:
            return {
                "interview_id": self.interview_id,
                "total_calls": len(self.call_records),
                "total_iterations": self.iteration_limiter.total_count,
                "loop_events": len(self.loop_events),
                "consecutive_degradations": self.consecutive_degradations,
                "is_halted": self.is_halted,
                "halt_reason": self.halt_reason,
                "agent_counts": dict(self.iteration_limiter.agent_counts),
                "recent_fingerprints": [
                    r.fingerprint() for r in self.call_records[-10:]
                ],
            }

    def get_training_data(self) -> list[dict]:
        """Export all loop events as training negative samples"""
        return [event.to_negative_sample() for event in self.loop_events]

    def get_full_log(self) -> list[dict]:
        """Export full call log for analysis"""
        return [r.to_dict() for r in self.call_records]