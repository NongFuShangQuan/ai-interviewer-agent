"""Admin API Routes - Manage interviews and view results"""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel, EmailStr

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.database import get_db, async_session_factory
from app.models.models import Interview, Candidate, Message, Evaluation

from app.services import interview_service, email_service

from app.core.config import get_settings



router = APIRouter(prefix="/api/admin", tags=["admin"])

settings = get_settings()





class CreateInterviewRequest(BaseModel):

    candidate_name: str

    candidate_email: str

    candidate_phone: str = ""

    position: str = ""

    resume_text: str = ""

    job_title: str

    job_description: str

    total_rounds: int = 5





class InterviewResponse(BaseModel):

    id: str

    candidate_name: str

    candidate_email: str

    job_title: str

    status: str

    current_round: int

    total_rounds: int

    overall_score: float | None = None

    recommendation: str | None = None

    created_at: str







@router.post("/interviews")

async def create_interview(

    req: CreateInterviewRequest,

    db: AsyncSession = Depends(get_db),

):

    """Create a new interview and send invitation email"""
    # Create candidate

    candidate = await interview_service.create_candidate(

        db,

        name=req.candidate_name,

        email=req.candidate_email,

        phone=req.candidate_phone,

        position=req.position,

        resume_text=req.resume_text,

    )



    # Create interview

    interview = await interview_service.create_interview(

        db,

        candidate_id=candidate.id,

        job_title=req.job_title,

        job_description=req.job_description,

        total_rounds=req.total_rounds,

    )



    # Get interview type from request (default to text)
    interview_type = getattr(req, 'interview_type', 'text') or 'text'

    # Build interview URL

    base_url = f"http://localhost:{settings.port}"

    interview_url = f"{base_url}/interview/{interview.token}"



    # Send invitation email

    email_sent = await email_service.send_invitation_email(

        to_email=req.candidate_email,

        candidate_name=req.candidate_name,

        job_title=req.job_title,

        interview_url=interview_url,

        total_rounds=req.total_rounds,

    )



    return {

        "success": True,

        "interview_id": interview.id,

        "token": interview.token,

        "interview_url": interview_url,

        "email_sent": email_sent,

        "message": f"面试已创建，邀请邮件已{'发送' if email_sent else '生成'}至 {req.candidate_email}",

    }





@router.get("/interviews")

async def list_interviews(db: AsyncSession = Depends(get_db)):

    """List all interviews with stats"""

    interviews = await interview_service.get_all_interviews(db)

    stats = await interview_service.get_interview_stats(db)



    result = []

    for iv in interviews:

        eval_data = iv.evaluation

        result.append({

            "id": iv.id,

            "candidate_name": iv.candidate.name if iv.candidate else "Unknown",

            "candidate_email": iv.candidate.email if iv.candidate else "",

            "job_title": iv.job_title,

            "status": iv.status,

            "current_round": iv.current_round,

            "total_rounds": iv.total_rounds,

            "overall_score": eval_data.overall_score if eval_data else None,

            "recommendation": eval_data.recommendation if eval_data else None,

            "interview_type": iv.interview_type if hasattr(iv, "interview_type") and iv.interview_type else "text",
            "created_at": iv.created_at.isoformat() if iv.created_at else "",

            "completed_at": iv.completed_at.isoformat() if iv.completed_at else None,

        })



    return {"interviews": result, "stats": stats}





@router.get("/interviews/{interview_id}")

async def get_interview_detail(

    interview_id: str,

    db: AsyncSession = Depends(get_db),

):

    """Get full interview details including messages and evaluation"""

    interview = await interview_service.get_interview_by_id(db, interview_id)

    if not interview:

        raise HTTPException(status_code=404, detail="Interview not found")



    messages = [

        {

            "round_num": msg.round_num,

            "role": msg.role,

            "content": msg.content,

            "created_at": msg.created_at.isoformat() if msg.created_at else "",

        }

        for msg in (interview.messages or [])

    ]



    eval_data = interview.evaluation

    evaluation = None

    if eval_data:

        evaluation = {

            "overall_score": eval_data.overall_score,

            "technical_score": eval_data.technical_score,

            "communication_score": eval_data.communication_score,

            "problem_solving_score": eval_data.problem_solving_score,

            "cultural_fit_score": eval_data.cultural_fit_score,

            "experience_score": eval_data.experience_score,

            "summary": eval_data.summary,

            "strengths": eval_data.strengths,

            "weaknesses": eval_data.weaknesses,

            "recommendation": eval_data.recommendation,

            "detailed_feedback": eval_data.detailed_feedback,

        }



    return {

        "id": interview.id,

        "candidate_name": interview.candidate.name if interview.candidate else "Unknown",

        "candidate_email": interview.candidate.email if interview.candidate else "",

        "job_title": interview.job_title,

        "job_description": interview.job_description,

        "status": interview.status,

        "current_round": interview.current_round,

        "total_rounds": interview.total_rounds,

        "messages": messages,

        "evaluation": evaluation,

        "created_at": interview.created_at.isoformat() if interview.created_at else "",

        "started_at": interview.started_at.isoformat() if interview.started_at else None,

        "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,

    }



import json, os



@router.get("/job-templates")

async def get_job_templates():

    """Return available job templates"""

    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "job_templates.json")

    with open(data_path, "r", encoding="utf-8") as f:

        return json.load(f)



@router.get("/guard/logs/{interview_id}")

async def get_guard_logs(interview_id: str, db: AsyncSession = Depends(get_db)):

    """Get tool call logs for a specific interview"""

    from app.models.models import ToolCallLog, LoopEventLog

    from sqlalchemy import desc



    # Tool call logs

    result = await db.execute(

        select(ToolCallLog)

        .where(ToolCallLog.interview_id == interview_id)

        .order_by(ToolCallLog.created_at)

    )

    call_logs = result.scalars().all()



    # Loop events

    result = await db.execute(

        select(LoopEventLog)

        .where(LoopEventLog.interview_id == interview_id)

        .order_by(LoopEventLog.created_at)

    )

    loop_logs = result.scalars().all()



    return {

        "interview_id": interview_id,

        "tool_calls": [

            {

                "id": log.id,

                "agent": log.agent_name,

                "tool": log.tool_name,

                "result": log.result,

                "duration_ms": log.duration_ms,

                "iteration": log.iteration,

                "turn": log.turn_num,

                "fingerprint": log.fingerprint,

                "error": log.error_msg,

                "params_summary": log.params_summary,

                "created_at": log.created_at.isoformat() if log.created_at else "",

            }

            for log in call_logs

        ],

        "loop_events": [

            {

                "id": log.id,

                "loop_type": log.loop_type,

                "pattern": log.pattern,

                "action": log.action_taken,

                "resolution": log.resolution,

                "calls_involved": log.calls_involved,

                "created_at": log.created_at.isoformat() if log.created_at else "",

            }

            for log in loop_logs

        ],

        "summary": {

            "total_calls": len(call_logs),

            "total_loops": len(loop_logs),

            "degraded_calls": sum(1 for l in call_logs if l.result == "degraded"),

            "blocked_calls": sum(1 for l in call_logs if l.result == "blocked"),

            "error_calls": sum(1 for l in call_logs if l.result == "error"),

            "avg_duration_ms": sum(l.duration_ms for l in call_logs) / len(call_logs) if call_logs else 0,

        },

    }





@router.get("/guard/training-data")

async def get_training_data(db: AsyncSession = Depends(get_db)):

    """Export loop events as negative samples for SFT/RL training"""

    from app.models.models import LoopEventLog



    result = await db.execute(select(LoopEventLog).order_by(LoopEventLog.created_at.desc()).limit(100))

    events = result.scalars().all()



    samples = []

    for event in events:

        if event.negative_sample:

            try:

                samples.append(json.loads(event.negative_sample))

            except Exception:

                pass



    return {

        "total": len(samples),

        "samples": samples,

        "usage": "These are negative samples from detected tool call loops. Use for SFT rejection sampling or RL reward shaping.",

    }





@router.get("/guard/stats")

async def get_guard_stats(db: AsyncSession = Depends(get_db)):

    """Get aggregate guard statistics across all interviews"""

    from app.models.models import ToolCallLog, LoopEventLog

    from sqlalchemy import func



    # Total tool calls

    total_calls = await db.execute(select(func.count(ToolCallLog.id)))

    total = total_calls.scalar() or 0



    # Calls by result

    result = await db.execute(

        select(ToolCallLog.result, func.count(ToolCallLog.id))

        .group_by(ToolCallLog.result)

    )

    by_result = {row[0]: row[1] for row in result.fetchall()}



    # Loop events by type

    result = await db.execute(

        select(LoopEventLog.loop_type, func.count(LoopEventLog.id))

        .group_by(LoopEventLog.loop_type)

    )

    loops_by_type = {row[0]: row[1] for row in result.fetchall()}



    # Total loop events

    total_loops_result = await db.execute(select(func.count(LoopEventLog.id)))

    total_loops = total_loops_result.scalar() or 0



    return {

        "total_tool_calls": total,

        "calls_by_result": by_result,

        "total_loop_events": total_loops,

        "loops_by_type": loops_by_type,

        "health_rate": round((by_result.get("success", 0) / total * 100), 1) if total > 0 else 100.0,

    }

@router.get("/avatar-sets")

async def get_avatar_sets():

    """Get available digital human avatar sets"""

    import os

    base_path = "app/static/images/digital_human"

    sets = []

    if os.path.exists(base_path):

        for d in sorted(os.listdir(base_path)):

            dir_path = os.path.join(base_path, d)

            if os.path.isdir(dir_path):

                files = os.listdir(dir_path)

                has_idle = "idle.jpg" in files

                if has_idle:

                    # Read first line of a metadata file if exists

                    sets.append({

                        "id": d,

                        "name": {

                            "set1_fay": "Fay 女性职业形象",

                            "set2_male": "男性职业形象", 

                            "set3_modern": "现代女性形象"

                        }.get(d, d),

                        "preview": f"/static/images/digital_human/{d}/idle.jpg",

                        "states": [f.replace('.jpg','') for f in files if f.endswith('.jpg')]

                    })

    return {"sets": sets}





# ===================== RAG Endpoints =====================



@router.get("/rag/status")

async def rag_status():

    """Get RAG system status"""

    try:

        from app.rag.manager import get_rag_manager

        rag = await get_rag_manager()

        return rag.get_status()

    except Exception as e:

        return {"initialized": False, "error": str(e)}





@router.post("/rag/reindex")

async def rag_reindex():

    """Re-index all RAG stores"""

    try:

        from app.rag.manager import get_rag_manager, RAGManager

        import app.rag.manager as mgr

        # Reset singleton to force re-initialization

        mgr._rag_manager = None

        rag = await get_rag_manager()

        return {"success": True, "status": rag.get_status()}

    except Exception as e:

        return {"success": False, "error": str(e)}





@router.get("/rag/question-bank")

async def rag_question_bank():

    """Get question bank metadata and questions"""

    import json

    import os

    bank_path = "app/data/rag/question_bank.json"

    if not os.path.exists(bank_path):

        return {"metadata": {"total_questions": 0}, "questions": []}

    with open(bank_path, "r", encoding="utf-8") as f:

        return json.load(f)





# ===================== Export Endpoints =====================



@router.get("/interviews/{interview_id}/export/json")

async def export_interview_json(interview_id: str):

    """Export interview result as JSON"""

    from fastapi.responses import Response

    from app.services.export_service import export_json

    async with async_session_factory() as db:

        result = await db.execute(select(Interview).where(Interview.id == interview_id))

        iv = result.scalar_one_or_none()

        if not iv:

            return {"error": "Interview not found"}

        

        cand_result = await db.execute(select(Candidate).where(Candidate.id == iv.candidate_id))

        cand = cand_result.scalar_one_or_none()

        

        eval_result = await db.execute(select(Evaluation).where(Evaluation.interview_id == interview_id))

        evaluation = eval_result.scalar_one_or_none()

        

        msg_result = await db.execute(

            select(Message).where(Message.interview_id == interview_id).order_by(Message.round_num)

        )

        messages = msg_result.scalars().all()

        

        data = {

            "candidate_name": cand.name if cand else "",

            "candidate_email": cand.email if cand else "",

            "job_title": iv.job_title,

            "status": iv.status,

            "created_at": str(iv.created_at),

            "evaluation": {

                "overall_score": evaluation.overall_score if evaluation else None,

                "technical_score": evaluation.technical_score if evaluation else None,

                "communication_score": evaluation.communication_score if evaluation else None,

                "problem_solving_score": evaluation.problem_solving_score if evaluation else None,

                "cultural_fit_score": evaluation.cultural_fit_score if evaluation else None,

                "experience_score": evaluation.experience_score if evaluation else None,

                "summary": evaluation.summary if evaluation else "",

                "strengths": evaluation.strengths if evaluation else "",

                "weaknesses": evaluation.weaknesses if evaluation else "",

                "recommendation": evaluation.recommendation if evaluation else "",

            } if evaluation else {},

            "messages": [

                {"round_num": m.round_num, "role": m.role, "content": m.content}

                for m in messages

            ],

        }

    

    json_str = export_json(data)

    return Response(content=json_str, media_type="application/json",

                   headers={"Content-Disposition": f"attachment; filename=interview_{interview_id}.json"})





@router.get("/interviews/{interview_id}/export/csv")

async def export_interview_csv(interview_id: str):

    """Export interview result as CSV"""

    from fastapi.responses import Response

    from app.services.export_service import export_csv

    # Reuse the same data gathering logic

    async with async_session_factory() as db:

        result = await db.execute(select(Interview).where(Interview.id == interview_id))

        iv = result.scalar_one_or_none()

        if not iv:

            return {"error": "Interview not found"}

        

        cand_result = await db.execute(select(Candidate).where(Candidate.id == iv.candidate_id))

        cand = cand_result.scalar_one_or_none()

        

        eval_result = await db.execute(select(Evaluation).where(Evaluation.interview_id == interview_id))

        evaluation = eval_result.scalar_one_or_none()

        

        msg_result = await db.execute(

            select(Message).where(Message.interview_id == interview_id).order_by(Message.round_num)

        )

        messages = msg_result.scalars().all()

        

        data = {

            "candidate_name": cand.name if cand else "",

            "job_title": iv.job_title,

            "status": iv.status,

            "created_at": str(iv.created_at),

            "evaluation": {

                "overall_score": evaluation.overall_score if evaluation else None,

                "recommendation": evaluation.recommendation if evaluation else "",

                "summary": evaluation.summary if evaluation else "",

                "strengths": evaluation.strengths if evaluation else "",

            } if evaluation else {},

            "messages": [

                {"round_num": m.round_num, "role": m.role, "content": m.content}

                for m in messages

            ],

        }

    

    csv_str = export_csv(data)

    return Response(content=csv_str, media_type="text/csv",

                   headers={"Content-Disposition": f"attachment; filename=interview_{interview_id}.csv"})





@router.get("/interviews/{interview_id}/export/html")

async def export_interview_html(interview_id: str):


    """Export interview result as HTML report"""

    from fastapi.responses import Response

    from app.services.export_service import export_html

    async with async_session_factory() as db:

        result = await db.execute(select(Interview).where(Interview.id == interview_id))

        iv = result.scalar_one_or_none()

        if not iv:

            return {"error": "Interview not found"}

        

        cand_result = await db.execute(select(Candidate).where(Candidate.id == iv.candidate_id))

        cand = cand_result.scalar_one_or_none()

        

        eval_result = await db.execute(select(Evaluation).where(Evaluation.interview_id == interview_id))

        evaluation = eval_result.scalar_one_or_none()

        

        msg_result = await db.execute(

            select(Message).where(Message.interview_id == interview_id).order_by(Message.round_num)

        )

        messages = msg_result.scalars().all()

        

        data = {

            "candidate_name": cand.name if cand else "",

            "job_title": iv.job_title,

            "status": iv.status,

            "created_at": str(iv.created_at),

            "evaluation": {

                "overall_score": evaluation.overall_score if evaluation else None,

                "technical_score": evaluation.technical_score if evaluation else None,

                "communication_score": evaluation.communication_score if evaluation else None,

                "problem_solving_score": evaluation.problem_solving_score if evaluation else None,

                "cultural_fit_score": evaluation.cultural_fit_score if evaluation else None,

                "experience_score": evaluation.experience_score if evaluation else None,

                "summary": evaluation.summary if evaluation else "",

                "strengths": evaluation.strengths if evaluation else "",

                "weaknesses": evaluation.weaknesses if evaluation else "",

                "recommendation": evaluation.recommendation if evaluation else "",

            } if evaluation else {},

            "messages": [

                {"round_num": m.round_num, "role": m.role, "content": m.content}

                for m in messages

            ],

        }

    

    html_str = export_html(data)

    return Response(content=html_str, media_type="text/html",

                   headers={"Content-Disposition": f"attachment; filename=interview_{interview_id}.html"})

