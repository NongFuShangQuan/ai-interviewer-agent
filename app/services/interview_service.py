"""Interview Service - Core business logic for managing interviews"""
import uuid
import secrets
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.models import (
    Candidate, Interview, Message, Evaluation, InterviewStatus
)
from app.core.config import get_settings

settings = get_settings()


async def create_candidate(
    db: AsyncSession,
    name: str,
    email: str,
    position: str = "",
    phone: str = "",
    resume_text: str = "",
) -> Candidate:
    """Create or get existing candidate"""
    result = await db.execute(select(Candidate).where(Candidate.email == email))
    candidate = result.scalar_one_or_none()

    if candidate is None:
        candidate = Candidate(
            name=name,
            email=email,
            position=position,
            phone=phone,
            resume_text=resume_text,
        )
        db.add(candidate)
        await db.flush()

    return candidate


async def create_interview(
    db: AsyncSession,
    candidate_id: str,
    job_title: str,
    job_description: str,
    total_rounds: int = 5,
) -> Interview:
    """Create a new interview session with access token"""
    token = secrets.token_urlsafe(32)
    interview = Interview(
        candidate_id=candidate_id,
        token=token,
        status=InterviewStatus.PENDING.value,
        total_rounds=total_rounds,
        job_title=job_title,
        job_description=job_description,
    )
    db.add(interview)
    await db.flush()
    return interview


async def get_interview_by_token(db: AsyncSession, token: str) -> Interview | None:
    """Get interview by access token"""
    result = await db.execute(
        select(Interview)
        .options(selectinload(Interview.candidate))
        .where(Interview.token == token)
    )
    return result.scalar_one_or_none()


async def get_interview_by_id(db: AsyncSession, interview_id: str) -> Interview | None:
    """Get interview by ID with all relations"""
    result = await db.execute(
        select(Interview)
        .options(
            selectinload(Interview.candidate),
            selectinload(Interview.messages),
            selectinload(Interview.evaluation),
        )
        .where(Interview.id == interview_id)
    )
    return result.scalar_one_or_none()


async def start_interview(db: AsyncSession, interview: Interview) -> Interview:
    """Mark interview as started"""
    interview.status = InterviewStatus.IN_PROGRESS.value
    interview.started_at = datetime.utcnow()
    interview.current_round = 1
    await db.flush()
    return interview


async def save_message(
    db: AsyncSession,
    interview_id: str,
    round_num: int,
    role: str,
    content: str,
) -> Message:
    """Save a message to the database"""
    message = Message(
        interview_id=interview_id,
        round_num=round_num,
        role=role,
        content=content,
    )
    db.add(message)
    await db.flush()
    return message


async def advance_round(db: AsyncSession, interview: Interview) -> Interview:
    """Move to next round"""
    interview.current_round += 1
    await db.flush()
    return interview


async def complete_interview(
    db: AsyncSession,
    interview: Interview,
    evaluation_data: dict,
) -> Evaluation:
    """Complete interview and save evaluation"""
    interview.status = InterviewStatus.COMPLETED.value
    interview.completed_at = datetime.utcnow()

    evaluation = Evaluation(
        interview_id=interview.id,
        overall_score=evaluation_data.get("overall_score", 0.0),
        technical_score=evaluation_data.get("technical_score", 0.0),
        communication_score=evaluation_data.get("communication_score", 0.0),
        problem_solving_score=evaluation_data.get("problem_solving_score", 0.0),
        cultural_fit_score=evaluation_data.get("cultural_fit_score", 0.0),
        experience_score=evaluation_data.get("experience_score", 0.0),
        summary=evaluation_data.get("summary", ""),
        strengths=evaluation_data.get("strengths", ""),
        weaknesses=evaluation_data.get("weaknesses", ""),
        recommendation=evaluation_data.get("recommendation", "pending"),
        detailed_feedback=evaluation_data.get("detailed_feedback", ""),
    )
    db.add(evaluation)
    await db.flush()
    return evaluation


async def get_all_interviews(db: AsyncSession) -> list:
    """Get all interviews with candidates and evaluations"""
    result = await db.execute(
        select(Interview)
        .options(
            selectinload(Interview.candidate),
            selectinload(Interview.evaluation),
        )
        .order_by(Interview.created_at.desc())
    )
    return list(result.scalars().all())


async def get_interview_stats(db: AsyncSession) -> dict:
    """Get interview statistics"""
    from sqlalchemy import func

    total = await db.execute(select(func.count(Interview.id)))
    completed = await db.execute(
        select(func.count(Interview.id)).where(
            Interview.status == InterviewStatus.COMPLETED.value
        )
    )
    in_progress = await db.execute(
        select(func.count(Interview.id)).where(
            Interview.status == InterviewStatus.IN_PROGRESS.value
        )
    )
    avg_score = await db.execute(
        select(func.avg(Evaluation.overall_score)).where(
            Evaluation.overall_score > 0
        )
    )

    return {
        "total_interviews": total.scalar() or 0,
        "completed": completed.scalar() or 0,
        "in_progress": in_progress.scalar() or 0,
        "average_score": round(avg_score.scalar() or 0, 1),
    }
