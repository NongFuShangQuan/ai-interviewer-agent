"""
RAG Retrievers - 4 RAG scenarios for interview system.

1. QuestionBankRetriever  - Smart question bank retrieval by job/skill
2. ResumeRetriever        - Resume deep-dive retrieval
3. EvaluationRefRetriever - Historical excellent interview reference
4. KnowledgeRetriever     - Job-related technical knowledge retrieval
"""
import json
import os
import time
import logging
from typing import Optional
from app.rag.vectorstore import SimpleVectorStore, EmbeddingClient

logger = logging.getLogger("rag.retrievers")

# Singleton embedding client
_embedding_client: Optional[EmbeddingClient] = None

def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


# ===================== 1. Smart Question Bank =====================

class QuestionBankRetriever:
    """
    Retrieve relevant interview questions based on job title and required skills.
    
    Usage:
        retriever = QuestionBankRetriever()
        await retriever.initialize()
        questions = await retriever.retrieve("Python高级开发工程师", "并发编程", top_k=3)
    """
    
    def __init__(self):
        self.store = SimpleVectorStore("question_bank", get_embedding_client())
        self._initialized = False
    
    async def initialize(self):
        """Load question bank and build vector index"""
        if self._initialized:
            return
        
        # Try loading persisted store
        if await self.store.load():
            self._initialized = True
            logger.info(f"QuestionBank: loaded {self.store.count} questions from cache")
            return
        
        # Build from scratch
        bank_path = "app/data/rag/question_bank.json"
        if not os.path.exists(bank_path):
            logger.warning("Question bank file not found")
            return
        
        with open(bank_path, "r", encoding="utf-8") as f:
            bank = json.load(f)
        
        documents = []
        for q in bank["questions"]:
            # Combine question + keywords + sample_answer for richer embedding
            text = f"{q['question']} {' '.join(q.get('keywords', []))} {q.get('sample_answer', '')}"
            documents.append({
                "text": text,
                "id": q["id"],
                "question": q["question"],
                "category": q["category"],
                "job_family": q["job_family"],
                "skill": q["skill"],
                "difficulty": q["difficulty"],
                "keywords": q.get("keywords", []),
                "sample_answer": q.get("sample_answer", ""),
            })
        
        await self.store.add_documents(documents, text_field="text")
        await self.store.persist()
        self._initialized = True
        logger.info(f"QuestionBank: built index with {len(documents)} questions")
    
    async def retrieve(self, job_title: str = "", skill: str = "", top_k: int = 5) -> list[dict]:
        """Retrieve questions relevant to job title and/or skill"""
        if not self._initialized:
            await self.initialize()
        
        if self.store.count == 0:
            return []
        
        # Build search query
        query_parts = []
        if job_title:
            query_parts.append(job_title)
        if skill:
            query_parts.append(skill)
        query = " ".join(query_parts) if query_parts else "通用面试问题"
        
        results = await self.store.search(query, top_k=top_k, threshold=0.05)
        return results
    
    async def retrieve_by_job_family(self, job_family: str, top_k: int = 5) -> list[dict]:
        """Retrieve questions by exact job family match, fallback to vector search"""
        if not self._initialized:
            await self.initialize()
        
        # First try exact match
        exact = [d for d in self.store.documents if d.get("job_family") == job_family]
        if exact:
            return exact[:top_k]
        
        # Fallback to vector search
        return await self.store.search(job_family, top_k=top_k, threshold=0.03)


# ===================== 2. Resume Deep-Dive =====================

class ResumeRetriever:
    """
    Index resume content and retrieve relevant sections for deep-dive questions.
    
    Usage:
        retriever = ResumeRetriever()
        await retriever.index_resume("候选人简历文本...")
        sections = await retriever.retrieve("项目经验", top_k=3)
    """
    
    def __init__(self):
        self.embedding_client = get_embedding_client()
        self.stores: dict[str, SimpleVectorStore] = {}  # per-interview stores
    
    async def index_resume(self, interview_id: str, resume_text: str):
        """Parse and index resume content"""
        store = SimpleVectorStore(f"resume_{interview_id}", self.embedding_client)
        
        # Split resume into semantic chunks
        chunks = self._split_resume(resume_text)
        
        documents = []
        for i, chunk in enumerate(chunks):
            documents.append({
                "text": chunk["text"],
                "section": chunk["section"],
                "chunk_id": i,
                "interview_id": interview_id,
            })
        
        if documents:
            await store.add_documents(documents, text_field="text")
            await store.persist()
            self.stores[interview_id] = store
            logger.info(f"Resume indexed for {interview_id}: {len(documents)} chunks")
    
    def _split_resume(self, text: str) -> list[dict]:
        """Split resume into semantic sections"""
        if not text:
            return []
        
        chunks = []
        current_section = "概览"
        
        # Split by common resume section headers
        section_headers = [
            "工作经历", "项目经验", "教育背景", "技能", "自我评价",
            "实习经历", "证书", "获奖", "开源项目", "技术栈",
            "Work Experience", "Projects", "Education", "Skills",
            "个人简介", "求职意向", "工作经验", "专业技能"
        ]
        
        lines = text.split("\n")
        current_chunk = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if current_chunk:
                    current_chunk.append("")
                continue
            
            # Check if this line is a section header
            is_header = False
            for header in section_headers:
                if header in line_stripped or line_stripped.rstrip("：:").endswith(header):
                    # Save current chunk
                    if current_chunk:
                        chunks.append({
                            "section": current_section,
                            "text": "\n".join(current_chunk).strip()
                        })
                    current_section = header
                    current_chunk = [line_stripped]
                    is_header = True
                    break
            
            if not is_header:
                current_chunk.append(line_stripped)
        
        # Last chunk
        if current_chunk:
            chunks.append({
                "section": current_section,
                "text": "\n".join(current_chunk).strip()
            })
        
        # If no sections found, split by paragraphs
        if len(chunks) <= 1 and len(text) > 500:
            paragraphs = text.split("\n\n")
            chunks = []
            for i, para in enumerate(paragraphs):
                if para.strip():
                    chunks.append({
                        "section": f"段落{i+1}",
                        "text": para.strip()
                    })
        
        # Filter empty chunks
        chunks = [c for c in chunks if c["text"].strip()]
        return chunks if chunks else [{"section": "简历", "text": text[:1000]}]
    
    async def retrieve(self, interview_id: str, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve relevant resume sections"""
        store = self.stores.get(interview_id)
        if not store:
            return []
        return await store.search(query, top_k=top_k, threshold=0.03)
    
    async def get_all_sections(self, interview_id: str) -> list[dict]:
        """Get all resume sections (for context building)"""
        store = self.stores.get(interview_id)
        if not store:
            return []
        return store.documents


# ===================== 3. Evaluation Reference =====================

class EvaluationRefRetriever:
    """
    Retrieve historical excellent interview cases as scoring reference.
    
    Indexes completed interview evaluations and retrieves similar ones
    when evaluating new interviews.
    """
    
    def __init__(self):
        self.store = SimpleVectorStore("eval_reference", get_embedding_client())
        self._initialized = False
    
    async def initialize(self):
        """Load historical evaluations"""
        if self._initialized:
            return
        
        if await self.store.load():
            self._initialized = True
            logger.info(f"EvalRef: loaded {self.store.count} references from cache")
            return
        
        self._initialized = True
    
    async def add_evaluation(self, interview_data: dict):
        """Index a completed interview evaluation as reference"""
        eval_data = interview_data.get("evaluation", {})
        if not eval_data:
            return
        
        # Build text for embedding
        text_parts = [
            f"职位: {interview_data.get('job_title', '')}",
            f"综合评分: {eval_data.get('overall_score', 0)}",
            f"技术评分: {eval_data.get('technical_score', 0)}",
            f"沟通评分: {eval_data.get('communication_score', 0)}",
            f"总结: {eval_data.get('summary', '')}",
            f"优势: {eval_data.get('strengths', '')}",
            f"不足: {eval_data.get('weaknesses', '')}",
        ]
        
        # Add interview transcript summary
        messages = interview_data.get("messages", [])
        for msg in messages:
            if msg.get("role") == "ai":
                text_parts.append(f"问题: {msg.get('content', '')[:100]}")
            else:
                text_parts.append(f"回答: {msg.get('content', '')[:200]}")
        
        doc = {
            "text": "\n".join(text_parts),
            "interview_id": interview_data.get("id", ""),
            "candidate_name": interview_data.get("candidate_name", ""),
            "job_title": interview_data.get("job_title", ""),
            "overall_score": eval_data.get("overall_score", 0),
            "recommendation": eval_data.get("recommendation", ""),
            "summary": eval_data.get("summary", ""),
            "strengths": eval_data.get("strengths", ""),
            "weaknesses": eval_data.get("weaknesses", ""),
        }
        
        await self.store.add_documents([doc], text_field="text")
        await self.store.persist()
    
    async def retrieve(self, job_title: str, query: str = "", top_k: int = 3) -> list[dict]:
        """Retrieve similar historical evaluations"""
        if not self._initialized:
            await self.initialize()
        
        if self.store.count == 0:
            return []
        
        search_query = f"{job_title} {query}".strip()
        return await self.store.search(search_query, top_k=top_k, threshold=0.05)
    
    async def get_high_score_references(self, job_title: str, min_score: float = 8.0) -> list[dict]:
        """Get high-scoring interview references for a job"""
        if not self._initialized:
            await self.initialize()
        
        results = await self.retrieve(job_title, top_k=10)
        return [r for r in results if r.get("overall_score", 0) >= min_score]


# ===================== 4. Knowledge Enhancement =====================

class KnowledgeRetriever:
    """
    Retrieve technical knowledge related to job descriptions.
    
    Builds a knowledge base from job descriptions and technical documentation,
    then retrieves relevant knowledge when generating interview questions.
    """
    
    def __init__(self):
        self.store = SimpleVectorStore("knowledge", get_embedding_client())
        self._initialized = False
    
    async def initialize(self):
        """Load knowledge base"""
        if self._initialized:
            return
        
        if await self.store.load():
            self._initialized = True
            logger.info(f"Knowledge: loaded {self.store.count} entries from cache")
            return
        
        # Build initial knowledge base from job templates
        await self._build_from_job_templates()
        self._initialized = True
    
    async def _build_from_job_templates(self):
        """Build knowledge base from job template data"""
        templates_path = "app/data/job_templates.json"
        if not os.path.exists(templates_path):
            logger.warning("Job templates not found")
            return
        
        with open(templates_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        
        documents = []
        for category in templates.get("categories", []):
            for job in category.get("jobs", []):
                # Extract knowledge from job description
                desc = job.get("description", "")
                title = job.get("title", "")
                if desc:
                    # Split long descriptions into chunks
                    chunks = self._split_knowledge(desc, title)
                    for chunk in chunks:
                        documents.append({
                            "text": chunk,
                            "job_title": title,
                            "category": category.get("name", ""),
                            "source": "job_template",
                        })
        
        if documents:
            await self.store.add_documents(documents, text_field="text")
            await self.store.persist()
            logger.info(f"Knowledge base built: {len(documents)} entries")
    
    def _split_knowledge(self, text: str, context: str = "") -> list[str]:
        """Split knowledge text into chunks"""
        if len(text) <= 300:
            return [f"{context} {text}".strip()]
        
        # Split by sentences or line breaks
        sentences = text.replace("。", "。\n").replace("；", "；\n").split("\n")
        chunks = []
        current = []
        current_len = 0
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if current_len + len(sent) > 300 and current:
                chunks.append(" ".join(current))
                current = [sent]
                current_len = len(sent)
            else:
                current.append(sent)
                current_len += len(sent)
        
        if current:
            chunks.append(" ".join(current))
        
        return chunks if chunks else [text[:500]]
    
    async def add_knowledge(self, text: str, job_title: str = "", source: str = "manual"):
        """Add custom knowledge entry"""
        doc = {
            "text": text,
            "job_title": job_title,
            "source": source,
        }
        await self.store.add_documents([doc], text_field="text")
        await self.store.persist()
    
    async def retrieve(self, job_title: str, query: str = "", top_k: int = 3) -> list[dict]:
        """Retrieve relevant technical knowledge"""
        if not self._initialized:
            await self.initialize()
        
        if self.store.count == 0:
            return []
        
        search_query = f"{job_title} {query}".strip() or job_title
        return await self.store.search(search_query, top_k=top_k, threshold=0.05)