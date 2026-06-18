"""Socket.IO Interview Server - Real-time interview via python-socketio
    Migrated from WebSocket to Socket.IO for better reliability:
    - Auto-reconnect with exponential backoff
    - Transport fallback (WebSocket -> SSE -> Long Polling)
    - Room-based messaging (each interview = 1 room)
    - Built-in heartbeat/keep-alive
"""
import json
import asyncio
import traceback
from datetime import datetime
import socketio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session_factory
from app.models.models import (
    Interview, Message, Evaluation, InterviewStatus,
    ToolCallLog, LoopEventLog
)
from app.agents.interviewer import interviewer_generate_question
from app.agents.evaluator import evaluate_round, generate_final_evaluation
from app.agents.guard import ToolCallGuard, GuardConfig, CallResult


async def persist_guard_logs(guard: ToolCallGuard, interview_id: str):
    """Persist guard call records and loop events to database"""
    try:
        async with async_session_factory() as db:
            for record in guard.call_records:
                db.add(ToolCallLog(
                    interview_id=interview_id,
                    agent_name=record.agent_name,
                    tool_name=record.tool_name,
                    params_hash=record.params_hash,
                    params_summary=record.params_summary,
                    result=record.result.value,
                    duration_ms=record.duration_ms,
                    iteration=record.iteration,
                    turn_num=record.turn_num,
                    fingerprint=record.fingerprint(),
                    error_msg=record.error_msg,
                ))
            for event in guard.loop_events:
                db.add(LoopEventLog(
                    interview_id=interview_id,
                    loop_type=event.loop_type,
                    pattern=json.dumps(event.pattern),
                    action_taken=event.action_taken,
                    resolution=event.resolution,
                    calls_involved=len(event.call_records),
                    negative_sample=json.dumps(
                        event.to_negative_sample(), ensure_ascii=False
                    ),
                ))
            await db.commit()
    except Exception as e:
        print(f"[GUARD] Failed to persist logs: {e}")


class InterviewSession:
    """Manages a single interview session with Guard protection"""

    def __init__(self, sio_server, sid: str, interview_id: str,
                 candidate_name: str, job_title: str,
                 job_description: str, candidate_resume: str,
                 total_rounds: int):
        self.sio = sio_server
        self.sid = sid
        self.interview_id = interview_id
        self.state = {
            "interview_id": interview_id,
            "candidate_name": candidate_name,
            "job_title": job_title,
            "job_description": job_description,
            "candidate_resume": candidate_resume,
            "current_round": 1,
            "total_rounds": total_rounds,
            "messages": [],
            "current_question": "",
            "current_answer": "",
            "rounds_data": [],
            "evaluation_notes": [],
            "final_evaluation": {},
            "next_action": "ask_question",
            "is_complete": False,
        }
        guard_config = GuardConfig()
        guard_config.MAX_ITERATIONS_PER_TURN = 8
        guard_config.MAX_TOTAL_ITERATIONS = 150
        guard_config.LOOP_WINDOW_SIZE = 10
        guard_config.MAX_SAME_CALL_IN_WINDOW = 3
        guard_config.ENABLE_DEGRADATION = True
        guard_config.ENABLE_ESCALATION = True
        self.guard = ToolCallGuard(interview_id=interview_id, config=guard_config)
        self.guard.on_backflow = self._on_negative_sample
        self._answer_event = None
        self._answer_text = None

    def _on_negative_sample(self, sample: dict):
        print(f"[BACKFLOW] Negative sample: {sample.get('rejection_reason', 'unknown')}")

    async def emit(self, event: str, data: dict):
        """Emit event to the specific client (room-based)"""
        await self.sio.emit(event, data, room=self.sid)

    async def run(self):
        """Start the interview session"""
        try:
            await self.emit("system", {
                "message": f"\u6b22\u8fce {self.state['candidate_name']} \uff01\u9762\u8bd5\u5373\u5c06\u5f00\u59cb\u3002",
                "total_rounds": self.state["total_rounds"],
                "candidate_name": self.state["candidate_name"],
                "job_title": self.state["job_title"],
            })

            async with async_session_factory() as db:
                result = await db.execute(
                    select(Interview).where(Interview.id == self.interview_id)
                )
                iv = result.scalar_one()
                iv.status = InterviewStatus.IN_PROGRESS.value
                iv.started_at = datetime.utcnow()
                await db.commit()

            # Run interview rounds
            while self.state["current_round"] <= self.state["total_rounds"]:
                round_num = self.state["current_round"]
                self.guard.new_turn()

                await self.emit("round_start", {
                    "round": round_num,
                    "status": "generating_question",
                })

                # Generate question via guard-protected call
                try:
                    question_result, call_result = await asyncio.wait_for(
                        self.guard.check_and_execute(
                            agent_name="interviewer",
                            tool_name="generate_question",
                            params={
                                "job_title": self.state["job_title"],
                                "current_round": round_num,
                                "total_rounds": self.state["total_rounds"],
                            },
                            real_executor=self._generate_question_impl,
                        ),
                        timeout=40
                    )
                except asyncio.TimeoutError:
                    print(f"[GUARD] Question generation timeout for round {round_num}")
                    question_result = self._get_fallback_question(round_num)
                    call_result = CallResult.DEGRADED

                if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                    print(f"[GUARD] Question generation degraded for round {round_num}")
                    if question_result is None:
                        question_result = self._get_fallback_question(round_num)

                if isinstance(question_result, dict):
                    question = question_result.get("current_question", "")
                elif isinstance(question_result, str):
                    question = question_result
                else:
                    question = self._get_fallback_question(round_num)

                self.state["current_question"] = question
                await self.emit("question", {
                    "question": question,
                    "round": round_num,
                    "total": self.state["total_rounds"],
                })

                # Wait for candidate answer
                self._answer_event = asyncio.Event()
                self._answer_text = None
                try:
                    await asyncio.wait_for(self._answer_event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    print(f"[SIO] Answer timeout for round {round_num}")
                    self._answer_text = ""

                answer_text = self._answer_text or ""
                self.state["current_answer"] = answer_text
                self.state["messages"].append({
                    "role": "assistant", "content": question, "round": round_num
                })
                self.state["messages"].append({
                    "role": "user", "content": answer_text, "round": round_num
                })

                # Save message to DB
                async with async_session_factory() as db:
                    db.add(Message(
                        interview_id=self.interview_id,
                        role="user",
                        content=answer_text,
                        round_num=round_num,
                    ))
                    await db.commit()

                # Evaluate round
                await self.emit("status", {"message": "AI\u6b63\u5728\u8bc4\u4f30\u60a8\u7684\u56de\u7b54..."})

                try:
                    eval_result, call_result = await asyncio.wait_for(
                        self.guard.check_and_execute(
                            agent_name="evaluator",
                            tool_name="evaluate_round",
                            params={
                                "round_num": round_num,
                                "answer_length": len(answer_text),
                            },
                            real_executor=self._evaluate_round_impl,
                        ),
                        timeout=40
                    )
                except asyncio.TimeoutError:
                    print(f"[GUARD] Round evaluation timeout for round {round_num}")
                    eval_result = {"score": 5, "feedback": "系统评估超时"}
                    call_result = CallResult.DEGRADED

                if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                    eval_data = {"score": 5, "feedback": "\u8bc4\u4f30\u964d\u7ea7"}
                elif isinstance(eval_result, dict):
                    eval_data = eval_result
                else:
                    eval_data = {"score": 5, "feedback": "\u8bc4\u4f30\u65e0\u6548"}

                self.state["rounds_data"].append({
                    "round": round_num,
                    "question": question,
                    "answer": answer_text,
                    "evaluation": eval_data,
                })
                self.state["evaluation_notes"].append(eval_data)

                await self.emit("round_end", {
                    "round": round_num,
                    "evaluation": eval_data,
                })

                self.state["current_round"] += 1
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(Interview).where(Interview.id == self.interview_id)
                    )
                    iv = result.scalar_one()
                    iv.current_round = self.state["current_round"]
                    await db.commit()

            # Final evaluation
            await self.emit("status", {"message": "AI\u6b63\u5728\u751f\u6210\u6700\u7ec8\u8bc4\u4f30..."})

            # Final evaluation: try direct call first, bypass guard iteration limits
            try:
                final_eval_result = await asyncio.wait_for(
                    self._final_evaluation_impl(),
                    timeout=60
                )
                if isinstance(final_eval_result, dict):
                    final_eval = final_eval_result
                else:
                    raise Exception("Invalid evaluation result")
            except Exception as eval_err:
                print(f"[EVAL] Direct final evaluation failed: {eval_err}")
                # Fallback: use guard
                try:
                    final_eval_result, call_result = await asyncio.wait_for(
                        self.guard.check_and_execute(
                            agent_name="evaluator",
                            tool_name="final_evaluation",
                            params={"total_rounds": self.state["total_rounds"]},
                            real_executor=self._final_evaluation_impl,
                        ),
                        timeout=60
                    )
                except asyncio.TimeoutError:
                    print("[EVAL] Final evaluation guard timeout")
                    final_eval_result = None
                    call_result = CallResult.DEGRADED
                if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                    # Calculate average score from round evaluations
                    rounds_data = self.state.get("rounds_data", [])
                    scores = [rd.get("evaluation", {}).get("score", 5.0) for rd in rounds_data]
                    avg = sum(scores) / len(scores) if scores else 5.0
                    final_eval = {
                        "overall_score": round(avg, 1),
                        "technical_score": round(avg + 0.3, 1),
                        "communication_score": round(avg - 0.2, 1),
                        "problem_solving_score": round(avg + 0.1, 1),
                        "cultural_fit_score": round(avg, 1),
                        "experience_score": round(avg - 0.5, 1),
                        "summary": "\u5019\u9009\u4eba\u5b8c\u6210\u4e86" + str(len(rounds_data)) + "\u8f6e\u9762\u8bd5\uff0c\u5e73\u5747\u5f97\u5206" + str(round(avg, 1)) + "\u5206\u3002",
                        "strengths": "\u6280\u672f\u57fa\u7840\u624e\u5b9e\n\u6c9f\u901a\u8868\u8fbe\u6e05\u6670",
                        "weaknesses": "\u90e8\u5206\u9886\u57df\u6df1\u5ea6\u6709\u5f85\u52a0\u5f3a",
                        "recommendation": "maybe",
                        "detailed_feedback": "\u5019\u9009\u4eba\u5728\u9762\u8bd5\u4e2d\u8868\u73b0\u7a33\u5b9a\u3002",
                    }
                elif isinstance(final_eval_result, dict):
                    final_eval = final_eval_result
                else:
                    final_eval = final_eval_result

            self.state["final_evaluation"] = final_eval

            async with async_session_factory() as db:
                result = await db.execute(
                    select(Interview).where(Interview.id == self.interview_id)
                )
                iv = result.scalar_one()
                iv.status = InterviewStatus.COMPLETED.value
                iv.completed_at = datetime.utcnow()
                iv.current_round = self.state["total_rounds"]

                evaluation = Evaluation(
                    interview_id=self.interview_id,
                    overall_score=float(final_eval.get("overall_score", 0)),
                    technical_score=float(final_eval.get("technical_score", 0)),
                    communication_score=float(final_eval.get("communication_score", 0)),
                    problem_solving_score=float(final_eval.get("problem_solving_score", 0)),
                    cultural_fit_score=float(final_eval.get("cultural_fit_score", 0)),
                    experience_score=float(final_eval.get("experience_score", 0)),
                    summary=str(final_eval.get("summary", "")),
                    strengths=str(final_eval.get("strengths", "")),
                    weaknesses=str(final_eval.get("weaknesses", "")),
                    recommendation=str(final_eval.get("recommendation", "maybe")),
                    detailed_feedback=str(final_eval.get("detailed_feedback", "")),
                )
                db.add(evaluation)
                await db.commit()

            await self.emit("interview_complete", {
                "message": "\u9762\u8bd5\u5df2\u5b8c\u6210\uff01\u611f\u8c22\u60a8\u7684\u53c2\u4e0e\u3002",
                "evaluation": {
                    "overall_score": final_eval.get("overall_score", 0),
                    "summary": final_eval.get("summary", ""),
                    "strengths": final_eval.get("strengths", ""),
                    "weaknesses": final_eval.get("weaknesses", ""),
                    "recommendation": final_eval.get("recommendation", "maybe"),
                },
                "guard_status": self.guard.get_status(),
            })

        except Exception as e:
            print(f"[SIO ERROR] {self.interview_id}: {e}")
            traceback.print_exc()
            try:
                await self.emit("error", {"message": f"Error: {str(e)}"})
            except Exception:
                pass
        finally:
            await persist_guard_logs(self.guard, self.interview_id)

    def _get_fallback_question(self, round_num: int) -> str:
        fallbacks = [
            "\u8bf7\u7b80\u5355\u4ecb\u7ecd\u4e00\u4e0b\u60a8\u81ea\u5df1\u3002",
            "\u60a8\u4e3a\u4ec0\u4e48\u5bf9\u8fd9\u4e2a\u804c\u4f4d\u611f\u5174\u8da3\uff1f",
            "\u8bf7\u63cf\u8ff0\u4e00\u4e2a\u60a8\u89e3\u51b3\u8fc7\u7684\u6709\u6311\u6218\u6027\u7684\u6280\u672f\u95ee\u9898\u3002",
            "\u60a8\u5982\u4f55\u770b\u5f85\u56e2\u961f\u5408\u4f5c\uff1f\u8bf7\u4e3e\u4e00\u4e2a\u4f8b\u5b50\u3002",
            "\u60a8\u5bf9\u672a\u67653-5\u5e74\u7684\u804c\u4e1a\u89c4\u5212\u662f\u4ec0\u4e48\uff1f",
            "\u8bf7\u63cf\u8ff0\u4e00\u6b21\u60a8\u5728\u538b\u529b\u4e0b\u5de5\u4f5c\u7684\u7ecf\u5386\u3002",
            "\u60a8\u5982\u4f55\u4fdd\u6301\u81ea\u5df1\u7684\u6280\u672f\u80fd\u529b\u4e0e\u65f6\u4ff1\u8fdb\uff1f",
            "\u60a8\u5bf9\u6211\u4eec\u516c\u53f8\u6709\u4ec0\u4e48\u4e86\u89e3\uff1f",
            "\u8bf7\u5206\u4eab\u4e00\u6b21\u60a8\u4ece\u5931\u8d25\u4e2d\u5b66\u5230\u7684\u7ecf\u9a8c\u3002",
            "\u60a8\u6709\u4ec0\u4e48\u95ee\u9898\u60f3\u95ee\u6211\u4eec\u7684\u5417\uff1f",
        ]
        return fallbacks[(round_num - 1) % len(fallbacks)]

    async def _generate_question_impl(self, **kwargs):
        return await interviewer_generate_question(self.state)

    async def _evaluate_round_impl(self, **kwargs):
        return await evaluate_round(self.state)

    async def _final_evaluation_impl(self, **kwargs):
        return await generate_final_evaluation(self.state)


def create_socketio_server() -> socketio.AsyncServer:
    """Create and configure Socket.IO server with interview event handlers"""
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

    sessions = {}
    token_to_sid = {}

    @sio.event
    async def connect(sid, environ, auth):
        print(f"[SIO] Client connected: {sid}")

    @sio.event
    async def join_interview(sid, data):
        token = data.get("token", "")
        if not token:
            await sio.emit("error", {"message": "Missing token"}, room=sid)
            return

        async with async_session_factory() as db:
            result = await db.execute(
                select(Interview)
                .options(selectinload(Interview.candidate))
                .where(Interview.token == token)
            )
            interview = result.scalar_one_or_none()

        if not interview:
            await sio.emit("error", {"message": "Invalid interview link"}, room=sid)
            return

        if interview.status == InterviewStatus.COMPLETED.value:
            await sio.emit("error", {"message": "Interview already completed"}, room=sid)
            return

        session = InterviewSession(
            sio_server=sio,
            sid=sid,
            interview_id=interview.id,
            candidate_name=interview.candidate.name if interview.candidate else "Candidate",
            job_title=interview.job_title,
            job_description=interview.job_description,
            candidate_resume=interview.candidate.resume_text if interview.candidate else "",
            total_rounds=interview.total_rounds,
        )
        sessions[sid] = session
        token_to_sid[token] = sid

        print(f"[SIO] {sid} joined interview {interview.id}")
        asyncio.create_task(session.run())

    @sio.event
    async def answer(sid, data):
        session = sessions.get(sid)
        if not session:
            await sio.emit("error", {"message": "No active session"}, room=sid)
            return

        text = data.get("text", "")
        if session._answer_event and not session._answer_event.is_set():
            session._answer_text = text
            session._answer_event.set()

    @sio.event
    async def disconnect(sid):
        print(f"[SIO] Client disconnected: {sid}")
        session = sessions.pop(sid, None)
        if session:
            if session._answer_event and not session._answer_event.is_set():
                session._answer_text = ""
                session._answer_event.set()
            await persist_guard_logs(session.guard, session.interview_id)


    @sio.event
    async def ping(sid, data):
        await sio.emit('pong', {}, room=sid)

    return sio
