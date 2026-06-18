"""WebSocket Interview Handler - Real-time AI interview via WebSocket
    Integrated with ToolCallGuard for loop protection
"""
import json
import traceback
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session_factory
from app.models.models import Interview, Message, Evaluation, InterviewStatus, ToolCallLog, LoopEventLog
from app.agents.interviewer import interviewer_generate_question
from app.agents.evaluator import evaluate_round, generate_final_evaluation
from app.agents.guard import ToolCallGuard, GuardConfig, CallResult
from app.core.config import get_settings

settings = get_settings()


async def persist_guard_logs(guard: ToolCallGuard, interview_id: str):
    """Persist guard call records and loop events to database"""
    try:
        async with async_session_factory() as db:
            # Save tool call logs
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

            # Save loop events as negative samples
            for event in guard.loop_events:
                import json as _json
                db.add(LoopEventLog(
                    interview_id=interview_id,
                    loop_type=event.loop_type,
                    pattern=_json.dumps(event.pattern),
                    action_taken=event.action_taken,
                    resolution=event.resolution,
                    calls_involved=len(event.call_records),
                    negative_sample=_json.dumps(event.to_negative_sample(), ensure_ascii=False),
                ))

            await db.commit()
    except Exception as e:
        print(f"[GUARD] Failed to persist logs: {e}")


class InterviewSession:
    """Manages a single interview WebSocket session with Guard protection"""

    def __init__(self, websocket: WebSocket, interview_id: str, candidate_name: str,
                 job_title: str, job_description: str, candidate_resume: str, total_rounds: int):
        self.ws = websocket
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
        # Initialize guard with tuned config
        guard_config = GuardConfig()
        guard_config.MAX_ITERATIONS_PER_TURN = 8
        guard_config.MAX_TOTAL_ITERATIONS = 150
        guard_config.LOOP_WINDOW_SIZE = 10
        guard_config.MAX_SAME_CALL_IN_WINDOW = 3
        guard_config.ENABLE_DEGRADATION = True
        guard_config.ENABLE_ESCALATION = True
        self.guard = ToolCallGuard(interview_id=interview_id, config=guard_config)

        # Wire up backflow logger
        self.guard.on_backflow = self._on_negative_sample

    def _on_negative_sample(self, sample: dict):
        """Callback: log negative sample for training data backflow"""
        print(f"[BACKFLOW] Negative sample: {sample.get('rejection_reason', 'unknown')}")

    async def send_message(self, msg_type: str, data: dict):
        await self.ws.send_json({"type": msg_type, "data": data})

    async def run(self):
        try:
            await self.send_message("system", {
                "message": f"欢迎 {self.state['candidate_name']}！面试即将开始。",
                "total_rounds": self.state["total_rounds"],
                "candidate_name": self.state['candidate_name'],
                "job_title": self.state['job_title'],
            })

            # Mark interview as started
            async with async_session_factory() as db:
                result = await db.execute(select(Interview).where(Interview.id == self.interview_id))
                iv = result.scalar_one()
                iv.status = InterviewStatus.IN_PROGRESS.value
                iv.started_at = datetime.utcnow()
                iv.current_round = 1
                await db.commit()

            # RAG: Initialize and index resume
            try:
                from app.rag.manager import get_rag_manager
                rag = await get_rag_manager()
                resume = self.state.get("candidate_resume", "")
                if resume:
                    await rag.index_resume(self.interview_id, resume)
                    await self.send_message("system", {
                        "message": "RAG知识库已加载，将提供更精准的面试问题。"
                    })
            except Exception as e:
                import logging
                logging.getLogger("interview_ws").debug(f"RAG init skipped: {e}")

            # Interview loop
            while self.state["current_round"] <= self.state["total_rounds"]:
                round_num = self.state["current_round"]
                self.guard.new_turn()  # Reset per-turn counters

                # 1) Generate question (guarded)
                await self.send_message("round_start", {
                    "round": round_num,
                    "total": self.state["total_rounds"],
                    "status": "generating_question",
                })

                question_result, call_result = await self.guard.check_and_execute(
                    agent_name="interviewer",
                    tool_name="generate_question",
                    params={
                        "job_title": self.state["job_title"],
                        "current_round": round_num,
                        "total_rounds": self.state["total_rounds"],
                    },
                    real_executor=self._generate_question_impl,
                )

                if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                    print(f"[GUARD] Question generation degraded for round {round_num}")
                    if question_result is None:
                        question_result = {
                            "current_question": f"请简单介绍一下您自己，以及您对{self.state['job_title']}这个职位的理解。",
                            "messages": [],
                            "next_action": "wait_for_answer",
                        }

                self.state.update(question_result)
                question = self.state["current_question"]

                self.state["rounds_data"].append({
                    "round_num": round_num,
                    "question": question,
                    "answer": "",
                    "evaluation_notes": "",
                    "round_score": 0.0,
                })

                async with async_session_factory() as db:
                    db.add(Message(
                        interview_id=self.interview_id,
                        round_num=round_num,
                        role="ai",
                        content=question,
                    ))
                    await db.commit()

                await self.send_message("question", {
                    "round": round_num,
                    "total": self.state["total_rounds"],
                    "question": question,
                })

                # 2) Wait for candidate answer
                raw = await self.ws.receive_text()
                payload = json.loads(raw)
                answer = payload.get("answer", "").strip()
                if not answer:
                    answer = "(no answer)"

                self.state["current_answer"] = answer
                if self.state["rounds_data"]:
                    self.state["rounds_data"][-1]["answer"] = answer

                async with async_session_factory() as db:
                    db.add(Message(
                        interview_id=self.interview_id,
                        round_num=round_num,
                        role="candidate",
                        content=answer,
                    ))
                    result = await db.execute(select(Interview).where(Interview.id == self.interview_id))
                    iv = result.scalar_one()
                    iv.current_round = round_num
                    await db.commit()

                # 3) Evaluate this round (guarded)
                await self.send_message("status", {
                    "message": "AI正在评估您的回答...",
                    "round": round_num,
                })

                eval_result, call_result = await self.guard.check_and_execute(
                    agent_name="evaluator",
                    tool_name="evaluate_round",
                    params={
                        "job_title": self.state["job_title"],
                        "current_round": round_num,
                        "total_rounds": self.state["total_rounds"],
                        "question": question,
                        "answer": answer,
                    },
                    real_executor=self._evaluate_round_impl,
                )

                if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                    print(f"[GUARD] Round evaluation degraded for round {round_num}")
                    if eval_result is None:
                        eval_result = {
                            "rounds_data": self.state["rounds_data"],
                            "evaluation_notes": self.state["evaluation_notes"],
                            "next_action": "ask_question",
                        }
                        if self.state["rounds_data"]:
                            eval_result["rounds_data"][-1]["evaluation_notes"] = "评估降级"
                            eval_result["rounds_data"][-1]["round_score"] = 5.0

                self.state.update(eval_result)

                round_score = 0
                if self.state["rounds_data"] and self.state["rounds_data"][-1].get("round_score"):
                    round_score = self.state["rounds_data"][-1]["round_score"]

                await self.send_message("round_end", {
                    "round": round_num,
                    "total": self.state["total_rounds"],
                    "round_score": round_score,
                })

                self.state["current_round"] = round_num + 1

            # 4) Final evaluation (guarded)
            await self.send_message("status", {"message": "面试结束，正在生成综合评估报告..."})
            self.state["is_complete"] = True

            final_result, call_result = await self.guard.check_and_execute(
                agent_name="evaluator",
                tool_name="final_evaluation",
                params={
                    "job_title": self.state["job_title"],
                    "job_description": self.state["job_description"],
                    "candidate_name": self.state["candidate_name"],
                    "rounds_data": self.state["rounds_data"],
                },
                real_executor=self._final_evaluation_impl,
            )

            if call_result in (CallResult.DEGRADED, CallResult.BLOCKED, CallResult.ERROR):
                print(f"[GUARD] Final evaluation degraded")
                if final_result is None:
                    final_result = {
                        "final_evaluation": {
                            "overall_score": 5.0,
                            "technical_score": 5.0,
                            "communication_score": 5.0,
                            "problem_solving_score": 5.0,
                            "cultural_fit_score": 5.0,
                            "experience_score": 5.0,
                            "summary": "评估系统异常，请人工复核。",
                            "strengths": "需要人工评估",
                            "weaknesses": "需要人工评估",
                            "recommendation": "maybe",
                            "detailed_feedback": "系统检测到异常，已降级为人工评估。",
                        },
                        "next_action": "complete",
                        "is_complete": True,
                    }

            self.state.update(final_result)
            final_eval = self.state["final_evaluation"]

            async with async_session_factory() as db:
                result = await db.execute(select(Interview).where(Interview.id == self.interview_id))
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

            await self.send_message("interview_complete", {
                "message": "面试已完成！感谢您的参与。",
                "evaluation": {
                    "overall_score": final_eval.get("overall_score", 0),
                    "summary": final_eval.get("summary", ""),
                    "strengths": final_eval.get("strengths", ""),
                    "weaknesses": final_eval.get("weaknesses", ""),
                    "recommendation": final_eval.get("recommendation", "maybe"),
                },
                "guard_status": self.guard.get_status(),
            })

        except WebSocketDisconnect:
            print(f"[WS] Disconnected: {self.interview_id}")
        except Exception as e:
            print(f"[WS ERROR] {self.interview_id}: {e}")
            traceback.print_exc()
            try:
                await self.send_message("error", {"message": f"Error: {str(e)}"})
            except Exception:
                pass
        finally:
            # Always persist guard logs
            await persist_guard_logs(self.guard, self.interview_id)

    # --- Wrapped tool implementations ---
    async def _generate_question_impl(self, **kwargs):
        """Actual question generation - called by guard"""
        return await interviewer_generate_question(self.state)

    async def _evaluate_round_impl(self, **kwargs):
        """Actual round evaluation - called by guard"""
        return await evaluate_round(self.state)

    async def _final_evaluation_impl(self, **kwargs):
        """Actual final evaluation - called by guard"""
        return await generate_final_evaluation(self.state)


async def handle_interview_websocket(websocket: WebSocket, token: str):
    """WebSocket endpoint handler for interviews"""
    await websocket.accept()

    async with async_session_factory() as db:
        result = await db.execute(
            select(Interview)
            .options(selectinload(Interview.candidate))
            .where(Interview.token == token)
        )
        interview = result.scalar_one_or_none()

    if not interview:
        await websocket.send_json({"type": "error", "data": {"message": "无效的面试链接"}})
        await websocket.close()
        return

    if interview.status == InterviewStatus.COMPLETED.value:
        await websocket.send_json({"type": "error", "data": {"message": "该面试已完成"}})
        await websocket.close()
        return

    session = InterviewSession(
        websocket=websocket,
        interview_id=interview.id,
        candidate_name=interview.candidate.name if interview.candidate else "Candidate",
        job_title=interview.job_title,
        job_description=interview.job_description,
        candidate_resume=interview.candidate.resume_text if interview.candidate else "",
        total_rounds=interview.total_rounds,
    )
    await session.run()