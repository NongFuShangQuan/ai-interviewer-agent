"""LangGraph Multi-Agent State Definition"""
from typing import TypedDict, Annotated, Literal
from langgraph.graph import add_messages
from dataclasses import dataclass, field


@dataclass
class InterviewRound:
    """Single round of interview data"""
    round_num: int
    question: str
    answer: str = ""
    evaluation_notes: str = ""
    round_score: float = 0.0


class InterviewState(TypedDict):
    """State shared across all agents in the interview workflow"""
    # Interview metadata
    interview_id: str
    candidate_name: str
    job_title: str
    job_description: str
    candidate_resume: str

    # Round tracking
    current_round: int
    total_rounds: int

    # Conversation
    messages: Annotated[list, add_messages]

    # Current round data
    current_question: str
    current_answer: str

    # Accumulated data
    rounds_data: list  # List of InterviewRound dicts
    evaluation_notes: list  # Accumulated evaluation notes per round

    # Final output
    final_evaluation: dict

    # Control flow
    next_action: str  # "ask_question", "wait_for_answer", "evaluate", "complete"
    is_complete: bool


class EvaluationResult(TypedDict):
    """Structured evaluation output"""
    overall_score: float
    technical_score: float
    communication_score: float
    problem_solving_score: float
    cultural_fit_score: float
    experience_score: float
    summary: str
    strengths: str
    weaknesses: str
    recommendation: Literal["hire", "maybe", "no_hire"]
    detailed_feedback: str
