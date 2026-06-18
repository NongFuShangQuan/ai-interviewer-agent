"""
RAG Manager - Unified interface for all RAG retrievers.

Provides a single entry point for agents to access RAG capabilities:
- question_bank: Smart question retrieval by job/skill
- resume: Resume content deep-dive
- eval_ref: Historical evaluation reference
- knowledge: Technical knowledge enhancement
"""
import logging
from typing import Optional
from app.rag.retrievers import (
    QuestionBankRetriever,
    ResumeRetriever,
    EvaluationRefRetriever,
    KnowledgeRetriever,
)

logger = logging.getLogger("rag.manager")


class RAGManager:
    """
    Unified RAG manager for the interview system.
    
    Usage:
        rag = RAGManager()
        await rag.initialize()
        
        # For interviewer: get questions
        questions = await rag.get_interview_questions("Python开发", "并发编程")
        
        # For interviewer: get resume context
        context = await rag.get_resume_context(interview_id, "项目经验")
        
        # For evaluator: get scoring reference
        refs = await rag.get_evaluation_reference("Python开发")
        
        # For interviewer: get knowledge
        knowledge = await rag.get_technical_knowledge("Python开发", "异步编程")
    """
    
    def __init__(self):
        self.question_bank = QuestionBankRetriever()
        self.resume_retriever = ResumeRetriever()
        self.eval_ref = EvaluationRefRetriever()
        self.knowledge = KnowledgeRetriever()
        self._initialized = False
    
    async def initialize(self):
        """Initialize all retrievers"""
        if self._initialized:
            return
        
        logger.info("Initializing RAG Manager...")
        await self.question_bank.initialize()
        await self.eval_ref.initialize()
        await self.knowledge.initialize()
        self._initialized = True
        logger.info("RAG Manager initialized successfully")
    
    # ---- Question Bank ----
    
    async def get_interview_questions(
        self, 
        job_title: str = "", 
        skill: str = "", 
        exclude_ids: list[str] = None,
        top_k: int = 5
    ) -> list[dict]:
        """
        Get relevant interview questions from the question bank.
        
        Returns questions sorted by relevance, excluding already-asked ones.
        """
        results = await self.question_bank.retrieve(job_title, skill, top_k=top_k + 5)
        
        # Filter out already-asked questions
        if exclude_ids:
            results = [r for r in results if r.get("id") not in exclude_ids]
        
        return results[:top_k]
    
    # ---- Resume Deep-Dive ----
    
    async def index_resume(self, interview_id: str, resume_text: str):
        """Index a candidate's resume for deep-dive questions"""
        if not resume_text:
            return
        await self.resume_retriever.index_resume(interview_id, resume_text)
    
    async def get_resume_context(
        self, 
        interview_id: str, 
        query: str, 
        top_k: int = 3
    ) -> list[dict]:
        """Get relevant resume sections for the query"""
        return await self.resume_retriever.retrieve(interview_id, query, top_k)
    
    # ---- Evaluation Reference ----
    
    async def add_evaluation_reference(self, interview_data: dict):
        """Index a completed interview as evaluation reference"""
        await self.eval_ref.add_evaluation(interview_data)
    
    async def get_evaluation_reference(
        self, 
        job_title: str, 
        query: str = "",
        top_k: int = 3
    ) -> list[dict]:
        """Get similar historical evaluations as scoring reference"""
        return await self.eval_ref.retrieve(job_title, query, top_k)
    
    async def get_high_score_references(
        self, 
        job_title: str, 
        min_score: float = 8.0
    ) -> list[dict]:
        """Get high-scoring references for calibration"""
        return await self.eval_ref.get_high_score_references(job_title, min_score)
    
    # ---- Knowledge Enhancement ----
    
    async def get_technical_knowledge(
        self, 
        job_title: str, 
        topic: str = "",
        top_k: int = 3
    ) -> list[dict]:
        """Get relevant technical knowledge for question generation"""
        return await self.knowledge.retrieve(job_title, topic, top_k)
    
    async def add_knowledge(self, text: str, job_title: str = ""):
        """Add custom knowledge to the knowledge base"""
        await self.knowledge.add_knowledge(text, job_title)
    
    # ---- Status ----
    
    def get_status(self) -> dict:
        """Get RAG system status"""
        return {
            "initialized": self._initialized,
            "question_bank_count": self.question_bank.store.count if self.question_bank.store else 0,
            "eval_ref_count": self.eval_ref.store.count if self.eval_ref.store else 0,
            "knowledge_count": self.knowledge.store.count if self.knowledge.store else 0,
            "embedding_cache_size": len(self.question_bank.store.embedding_client._cache) if self.question_bank.store else 0,
        }


# Singleton instance
_rag_manager: Optional[RAGManager] = None

async def get_rag_manager() -> RAGManager:
    """Get or create the RAG manager singleton"""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
        await _rag_manager.initialize()
    return _rag_manager