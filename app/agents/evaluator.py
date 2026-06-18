"""Evaluator Agent - Evaluates candidate responses and generates final scores"""
import json
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
from app.core.cache import get_cache

settings = get_settings()

ROUND_EVALUATOR_PROMPT = """你是一位专业的面试评估专家。请对候选人的回答进行实时评估。

## 当前信息
- 职位：{job_title}
- 第 {current_round} 轮（共 {total_rounds} 轮）

## 本轮问题
{question}

## 候选人回答
{answer}

## 评估要求
请对本轮回答进行简要评估，输出JSON格式：
{{
    "round_score": 1-10的分数,
    "evaluation_notes": "本轮评估要点（50字以内）"
}}

只输出JSON，不要输出其他内容，不要用markdown代码块包裹。"""


FINAL_EVALUATOR_PROMPT = """你是一位资深的面试评估专家。请根据完整的面试记录，对候选人进行全面评估。

## 职位信息
- 职位：{job_title}
- 职位描述：{job_description}

## 候选人信息
- 姓名：{candidate_name}
- 简历：{candidate_resume}

## 完整面试记录
{interview_transcript}

## 评估记录
{evaluation_notes}

## 评分标准
请从以下6个维度进行评分（每项0-10分，可以有小数）：
1. **技术能力** (technical_score)：专业知识深度和广度
2. **沟通表达** (communication_score)：表达清晰度、逻辑性
3. **问题解决** (problem_solving_score)：分析和解决问题的能力
4. **文化匹配** (cultural_fit_score)：团队协作、价值观匹配
5. **工作经验** (experience_score)：相关经验的丰富程度
6. **综合评分** (overall_score)：整体表现的加权评分

{rag_context}

## 输出要求
请直接输出以下JSON格式，不要用markdown代码块包裹，不要输出任何其他文字：
{{
    "overall_score": 7.5,
    "technical_score": 8.0,
    "communication_score": 7.0,
    "problem_solving_score": 7.5,
    "cultural_fit_score": 8.0,
    "experience_score": 6.5,
    "summary": "候选人整体表现总结（100-200字中文）",
    "strengths": "候选人主要优势（分点列出，中文）",
    "weaknesses": "候选人不足之处（分点列出，中文）",
    "recommendation": "hire/maybe/no_hire",
    "detailed_feedback": "详细反馈（200-300字中文），包含具体的回答引用和分析"
}}"""


def extract_json_from_text(text: str) -> dict | None:
    """Robustly extract JSON from LLM response that may contain markdown, text, etc."""
    if not text:
        return None

    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block ```json ... ``` or ``` ... ```
    patterns = [
        r'```json\s*\n?(.*?)\n?\s*```',
        r'```\s*\n?(.*?)\n?\s*```',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find the first { ... } block
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text[brace_start:brace_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def create_evaluator_agent():
    """Create the Evaluator Agent"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
    )
    return llm


async def evaluate_round(state: dict) -> dict:
    """Evaluate the candidate's answer for the current round"""
    import random
    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-your"):
        eval_data = {
            "round_score": round(random.uniform(6.0, 9.0), 1),
            "evaluation_notes": "Mock evaluation note for round " + str(state.get("current_round", 1)),
        }
    else:
        agent = create_evaluator_agent()
        prompt = ROUND_EVALUATOR_PROMPT.format(
            job_title=state.get("job_title", ""),
            current_round=state.get("current_round", 1),
            total_rounds=state.get("total_rounds", 10),
            question=state.get("current_question", ""),
            answer=state.get("current_answer", ""),
        )
        cache = get_cache()
        current_answer = state.get("current_answer", "")
        cache_key = f"eval_r{state.get('current_round', 1)}:{current_answer[:200]}"
        cached = await cache.get("evaluator_round", cache_key)
        if cached and isinstance(cached, dict):
            eval_data = cached
        else:
            try:
                response = await asyncio.wait_for(
                    agent.ainvoke([SystemMessage(content=prompt)]),
                    timeout=30
                )
            except asyncio.TimeoutError:
                logger.warning("Round evaluation LLM timeout (30s)")
                return {
                    "round_score": 5.0,
                    "evaluation_notes": "\u7cfb\u7edf\u8bc4\u4f30\u8d85\u65f6\uff0c\u91c7\u7528\u9ed8\u8ba4\u8bc4\u5206",
                }
            eval_data = extract_json_from_text(response.content)
            if not eval_data:
                eval_data = {
                    "round_score": 5.0,
                    "evaluation_notes": response.content[:100] if response.content else "evaluation parse error",
                }
            if isinstance(eval_data, dict):
                await cache.put("evaluator_round", cache_key, eval_data)

    rounds_data = list(state.get("rounds_data", []))
    if rounds_data:
        rounds_data[-1]["evaluation_notes"] = eval_data.get("evaluation_notes", "")
        rounds_data[-1]["round_score"] = eval_data.get("round_score", 5.0)

    evaluation_notes = list(state.get("evaluation_notes", []))
    evaluation_notes.append(
        f"R{state.get('current_round', 1)}: {eval_data.get('evaluation_notes', '')} (score: {eval_data.get('round_score', 5.0)})"
    )

    return {
        "rounds_data": rounds_data,
        "evaluation_notes": evaluation_notes,
        "next_action": "ask_question",
    }


async def generate_final_evaluation(state: dict) -> dict:
    """Generate comprehensive final evaluation after all rounds"""
    rounds_data = state.get("rounds_data", [])
    round_scores = [rd.get("round_score", 5.0) for rd in rounds_data if rd.get("round_score")]
    avg = sum(round_scores) / len(round_scores) if round_scores else 7.0

    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-your"):
        eval_result = {
            "overall_score": round(avg, 1),
            "technical_score": round(avg + 0.3, 1),
            "communication_score": round(avg - 0.2, 1),
            "problem_solving_score": round(avg + 0.1, 1),
            "cultural_fit_score": round(avg, 1),
            "experience_score": round(avg - 0.5, 1),
            "summary": f"候选人完成了{len(rounds_data)}轮面试，平均得分{round(avg, 1)}分。展现了扎实的技术基础和良好的沟通能力。",
            "strengths": "- 技术基础扎实\n- 沟通表达清晰\n- 解决问题思路清晰",
            "weaknesses": "- 部分领域深度有待加强\n- 行业经验需要积累",
            "recommendation": "maybe",
            "detailed_feedback": f"候选人在面试中表现稳定，平均得分{round(avg, 1)}分。",
        }
    else:
        agent = create_evaluator_agent()
        transcript_parts = []
        for rd in rounds_data:
            transcript_parts.append(f"  Q: {str(rd.get('question', ''))}")
            transcript_parts.append(f"  A: {str(rd.get('answer', ''))}")
            transcript_parts.append(f"  Score: {rd.get('round_score', 'N/A')}")
            transcript_parts.append("")
        interview_transcript = "\n".join(transcript_parts)
        evaluation_notes_text = "\n".join(state.get("evaluation_notes", []))

        # RAG: Get evaluation reference context
        rag_context = ""
        try:
            from app.rag.manager import get_rag_manager
            rag = await get_rag_manager()
            refs = await rag.get_evaluation_reference(
                state.get("job_title", ""),
                query=f"技术能力 沟通表达 综合评分",
                top_k=2
            )
            if refs:
                rag_parts = ["## 历史优秀面试参考（用于评分校准）"]
                for ref in refs:
                    score = ref.get("overall_score", 0)
                    if score >= 7.0:
                        rag_parts.append(
                            f"- 职位: {ref.get('job_title', '')}, "
                            f"评分: {score}, "
                            f"推荐: {ref.get('recommendation', '')}, "
                            f"总结: {ref.get('summary', '')[:100]}"
                        )
                rag_context = "\n".join(rag_parts)
        except Exception as e:
            import logging
            logging.getLogger("agent.evaluator").debug(f"RAG eval reference unavailable: {e}")

        prompt = FINAL_EVALUATOR_PROMPT.format(
            job_title=state.get("job_title", ""),
            job_description=state.get("job_description", ""),
            candidate_name=state.get("candidate_name", ""),
            candidate_resume=state.get("candidate_resume", ""),
            interview_transcript=interview_transcript,
            evaluation_notes=evaluation_notes_text,
            rag_context=rag_context,
        )
        try:
            response = await asyncio.wait_for(
                agent.ainvoke([SystemMessage(content=prompt)]),
                timeout=45
            )
        except asyncio.TimeoutError:
            import logging
            logging.getLogger('agent.evaluator').warning('Final evaluation LLM timeout (45s)')
            return {
                'overall_score': round(avg, 1),
                'technical_score': round(avg, 1),
                'communication_score': round(avg, 1),
                'problem_solving_score': round(avg, 1),
                'cultural_fit_score': round(avg, 1),
                'experience_score': round(avg, 1),
                'summary': '最终评估生成超时，已根据各轮得分计算平均分。',
                'strengths': '待补充',
                'weaknesses': '待补充',
                'recommendation': 'maybe',
                'detailed_feedback': '最终评估生成超时，平均得分' + str(round(avg, 1)) + '分。',
            }
        eval_result = extract_json_from_text(response.content)
        if not eval_result:
            # Failed to parse JSON - use fallback with whatever text we got
            raw_text = response.content or "评估生成失败"
            eval_result = {
                "overall_score": round(avg, 1),
                "technical_score": round(avg, 1),
                "communication_score": round(avg, 1),
                "problem_solving_score": round(avg, 1),
                "cultural_fit_score": round(avg, 1),
                "experience_score": round(avg, 1),
                "summary": raw_text[:500],
                "strengths": "待补充",
                "weaknesses": "待补充",
                "recommendation": "maybe",
                "detailed_feedback": raw_text,
            }

        # Ensure all score fields are valid floats
        for key in ["overall_score", "technical_score", "communication_score",
                     "problem_solving_score", "cultural_fit_score", "experience_score"]:
            try:
                eval_result[key] = float(eval_result.get(key, avg))
            except (TypeError, ValueError):
                eval_result[key] = round(avg, 1)

        # Ensure string fields exist
        for key in ["summary", "strengths", "weaknesses", "recommendation", "detailed_feedback"]:
            if not eval_result.get(key):
                eval_result[key] = "待补充" if key in ("strengths", "weaknesses") else "maybe" if key == "recommendation" else ""

        # Validate recommendation
        if eval_result.get("recommendation") not in ("hire", "maybe", "no_hire"):
            eval_result["recommendation"] = "maybe"

    # RAG: Index this evaluation as future reference
    try:
        from app.rag.manager import get_rag_manager
        rag = await get_rag_manager()
        await rag.add_evaluation_reference({
            "id": state.get("interview_id", ""),
            "candidate_name": state.get("candidate_name", ""),
            "job_title": state.get("job_title", ""),
            "evaluation": eval_result,
            "messages": [{"role": "ai" if i % 2 == 0 else "candidate", "content": m}
                        for i, m in enumerate(state.get("messages", []))],
        })
    except Exception as e:
        import logging
        logging.getLogger("agent.evaluator").debug(f"RAG eval indexing skipped: {e}")

    return {
        "final_evaluation": eval_result,
        "next_action": "complete",
        "is_complete": True,
    }
