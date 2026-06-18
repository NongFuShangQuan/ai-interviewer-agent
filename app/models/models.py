"""Database Models for AI Interview System"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class InterviewStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interviews: Mapped[list["Interview"]] = relationship(back_populates="candidate")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=InterviewStatus.PENDING.value
    )
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    total_rounds: Mapped[int] = mapped_column(Integer, default=10)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    job_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interview_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")  # text, video, live
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship(back_populates="interviews")
    messages: Mapped[list["Message"]] = relationship(back_populates="interview", order_by="Message.round_num")
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="interview", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    round_num: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "ai" or "candidate"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interview: Mapped["Interview"] = relationship(back_populates="messages")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), unique=True, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    technical_score: Mapped[float] = mapped_column(Float, default=0.0)
    communication_score: Mapped[float] = mapped_column(Float, default=0.0)
    problem_solving_score: Mapped[float] = mapped_column(Float, default=0.0)
    cultural_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    strengths: Mapped[str] = mapped_column(Text, default="")
    weaknesses: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(50), default="pending")  # hire, maybe, no_hire
    detailed_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interview: Mapped["Interview"] = relationship(back_populates="evaluation")

class ToolCallLog(Base):
    """Records every tool call for monitoring and analysis"""
    __tablename__ = "tool_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    params_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    params_summary: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # success/error/degraded/blocked
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    turn_num: Mapped[int] = mapped_column(Integer, default=0)
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LoopEventLog(Base):
    """Records detected loop events - negative samples for training"""
    __tablename__ = "loop_event_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False, index=True)
    loop_type: Mapped[str] = mapped_column(String(50), nullable=False)  # exact_repeat/pattern_repeat/rapid_fire/max_iterations
    pattern: Mapped[str] = mapped_column(Text, default="")  # JSON array of fingerprints
    action_taken: Mapped[str] = mapped_column(String(20), nullable=False)  # degraded/escalated/halted
    resolution: Mapped[str] = mapped_column(Text, default="")
    calls_involved: Mapped[int] = mapped_column(Integer, default=0)
    negative_sample: Mapped[str] = mapped_column(Text, default="")  # JSON for SFT/RL training
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)