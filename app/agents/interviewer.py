"""Interviewer Agent - Conducts the AI interview with RAG enhancement"""
import logging
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
from app.core.cache import get_cache

logger = logging.getLogger("agent.interviewer")
settings = get_settings()

INTERVIEWER_SYSTEM_PROMPT = """你是一位专业的AI面试官，名叫"小智"。你的职责是对应聘者进行专业、友好的面试。

## 你的角色
- 你是一位经验丰富、友善专业的面试官
- 你正在为"{job_title}"这个职位面试候选人
- 你需要通过{total_rounds}轮问答来全面了解候选人

## 职位描述
{job_description}

## 候选人简历
{candidate_resume}

{rag_context}

## 面试规则
1. 每轮只问一个问题，问题要清晰具体
2. 根据候选人的回答进行追问或切换话题
3. 问题应该涵盖：技术能力、项目经验、问题解决能力、团队协作、职业规划等
4. 语气要专业但友善，让候选人感到舒适
5. 第一轮用简短的自我介绍和暖场问题开始
6. 最后一轮可以问候选人是否有问题想问
7. 优先参考下方提供的"参考题库"中的问题，但要根据对话上下文自然地调整表述
8. 如果有"简历深挖"提示，优先针对候选人的具体经历追问

## 当前状态
- 当前是第 {current_round} 轮（共 {total_rounds} 轮）
- 之前的对话历史会提供给你参考

## 重要
- 只输出你作为面试官的下一个问题
- 不要输出任何其他内容
- 保持问题简洁明了，不超过3句话
"""


def create_interviewer_agent():
    """Create the Interviewer Agent using ChatOpenAI"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.7,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
    )
    return llm


async def build_interviewer_prompt(state: dict) -> list:
    """Build the prompt for the interviewer based on current state, with RAG context"""
    
    # Build RAG context
    rag_parts = []
    
    # Try to get RAG context (gracefully degrade if RAG not available)
    try:
        from app.rag.manager import get_rag_manager
        rag = await get_rag_manager()
        
        job_title = state.get("job_title", "")
        interview_id = state.get("interview_id", "")
        current_round = state.get("current_round", 1)
        asked_ids = state.get("_asked_question_ids", [])
        
        # 1. Question Bank - get relevant questions
        questions = await rag.get_interview_questions(
            job_title=job_title,
            exclude_ids=asked_ids,
            top_k=3
        )
        if questions:
            rag_parts.append("## 参考题库（可参考但不必完全照搬）")
            for i, q in enumerate(questions, 1):
                difficulty = {"easy": "基础", "medium": "中等", "hard": "高级"}.get(q.get("difficulty", ""), "")
                rag_parts.append(f"{i}. [{difficulty}] {q['question']}")
                if q.get("keywords"):
                    rag_parts.append(f"   关键词: {', '.join(q['keywords'][:5])}")
        
        # 2. Resume deep-dive - get relevant resume sections
        if interview_id:
            resume_context = await rag.get_resume_context(interview_id, "项目经验 技术栈", top_k=2)
            if resume_context:
                rag_parts.append("\n## 简历深挖提示")
                for ctx in resume_context:
                    section = ctx.get("section", "")
                    text = ctx.get("text", "")[:200]
                    score = ctx.get("_score", 0)
                    if score > 0.3:
                        rag_parts.append(f"- [{section}] {text}")
        
        # 3. Knowledge enhancement - get relevant technical knowledge
        knowledge = await rag.get_technical_knowledge(job_title, top_k=2)
        if knowledge:
            rag_parts.append("\n## 技术知识参考")
            for k in knowledge:
                text = k.get("text", "")[:150]
                rag_parts.append(f"- {text}")
        
    except Exception as e:
        logger.debug(f"RAG context unavailable (degraded mode): {e}")
    
    rag_context = "\n".join(rag_parts) if rag_parts else ""
    
    system_msg = INTERVIEWER_SYSTEM_PROMPT.format(
        job_title=state.get("job_title", ""),
        job_description=state.get("job_description", ""),
        candidate_resume=state.get("candidate_resume", "暂无简历信息"),
        total_rounds=state.get("total_rounds", 10),
        current_round=state.get("current_round", 1),
        rag_context=rag_context,
    )

    messages = [SystemMessage(content=system_msg)]

    # Add conversation history
    rounds_data = state.get("rounds_data", [])
    for rd in rounds_data:
        if rd.get("question"):
            messages.append(AIMessage(content=rd["question"]))
        if rd.get("answer"):
            messages.append(HumanMessage(content=rd["answer"]))

    return messages


MOCK_QUESTIONS = [
    "您好！欢迎参加面试。请先做一个简短的自我介绍，说说您的背景和为什么对这个职位感兴趣？",
    "您最近参与的一个项目是什么？能聊聊您在其中扮演的角色和遇到的挑战吗？",
    "能描述一下您解决过的一个比较棘手的技术问题吗？您的思路是怎样的？",
    "在团队协作中，如果和同事在技术方案上有分歧，您通常怎么处理？",
    "您平时是怎么学习新技术的？能举个最近的例子吗？",
    "对于代码质量，您有哪些实践和习惯？",
    "如果让您从零开始设计一个系统，您会考虑哪些方面？",
    "您对这个职位最期待的是什么？",
    "您觉得自己最大的优势和需要改进的地方分别是什么？",
    "最后，您有什么想问我们的吗？",
]


async def interviewer_generate_question(state: dict) -> dict:
    """Interviewer agent generates the next question (with RAG enhancement)"""
    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-your"):
        # Mock mode - use predefined questions
        round_num = state.get("current_round", 1) - 1
        question = MOCK_QUESTIONS[round_num % len(MOCK_QUESTIONS)]
    else:
        # Index resume on first round (for RAG deep-dive)
        current_round = state.get("current_round", 1)
        if current_round == 1:
            try:
                from app.rag.manager import get_rag_manager
                rag = await get_rag_manager()
                resume = state.get("candidate_resume", "")
                interview_id = state.get("interview_id", "")
                if resume and interview_id:
                    await rag.index_resume(interview_id, resume)
                    logger.info(f"Resume indexed for interview {interview_id}")
            except Exception as e:
                logger.debug(f"Resume indexing failed (degraded): {e}")
        
        agent = create_interviewer_agent()
        messages = await build_interviewer_prompt(state)
        # Check cache first
        cache = get_cache()
        prompt_hash = str([(m.type, m.content[:100]) for m in messages])
        cached = await cache.get("interviewer", prompt_hash)
        if cached and isinstance(cached, str) and len(cached) > 10:
            logger.info("Cache HIT for interviewer question")
            question = cached
        else:
            try:
                response = await asyncio.wait_for(
                    agent.ainvoke(messages),
                    timeout=30
                )
                question = response.content
                # Cache the response
                await cache.put("interviewer", prompt_hash, question)
            except asyncio.TimeoutError:
                logger.warning('Interviewer LLM timeout (30s), using fallback')
                round_num = state.get('current_round', 1) - 1
                question = MOCK_QUESTIONS[round_num % len(MOCK_QUESTIONS)]

    return {
        "current_question": question,
        "messages": [AIMessage(content=question)],
        "next_action": "wait_for_answer",
    }