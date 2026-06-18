"""Coordinator Agent - Orchestrates the multi-agent interview workflow using LangGraph"""
from langgraph.graph import StateGraph, END
from app.agents.state import InterviewState
from app.agents.interviewer import interviewer_generate_question
from app.agents.evaluator import evaluate_round, generate_final_evaluation


def should_continue_or_end(state: dict) -> str:
    """Decide whether to continue interviewing or end"""
    if state.get("is_complete", False):
        return "final_evaluation"
    if state.get("current_round", 0) >= state.get("total_rounds", 10):
        return "final_evaluation"
    return "interviewer"


def route_after_question(state: dict) -> str:
    """After question is asked, wait for candidate answer"""
    return "wait_for_answer"


def build_interview_graph():
    """
    Build the LangGraph multi-agent interview workflow.

    Flow:
    coordinator -> interviewer -> [wait for answer] -> evaluator -> coordinator
    ... repeat for N rounds ...
    coordinator -> final_evaluation -> END
    """
    workflow = StateGraph(InterviewState)

    # Add agent nodes
    workflow.add_node("interviewer", interviewer_generate_question)
    workflow.add_node("evaluator", evaluate_round)
    workflow.add_node("final_evaluation", generate_final_evaluation)

    # Set entry point
    workflow.set_entry_point("interviewer")

    # After interviewer asks question -> external input needed (candidate answer)
    # The graph pauses here; candidate answer is injected externally
    workflow.add_edge("interviewer", END)

    # After candidate answer is injected and evaluator runs
    workflow.add_conditional_edges(
        "evaluator",
        should_continue_or_end,
        {
            "interviewer": "interviewer",
            "final_evaluation": "final_evaluation",
        },
    )

    # After final evaluation -> END
    workflow.add_edge("final_evaluation", END)

    return workflow.compile()


# Singleton graph instance
_interview_graph = None


def get_interview_graph():
    """Get or create the interview graph singleton"""
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = build_interview_graph()
    return _interview_graph
