from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs) -> bool:
        return False


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() in ["agent", "agents"] else SCRIPT_DIR
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

print(f"加载 .env: {ENV_PATH} (存在: {ENV_PATH.exists()})")
load_dotenv(dotenv_path=ENV_PATH, override=True)


DEFAULT_RESUME = (
    "Candidate Zhang San has 3 years of Python backend experience, "
    "is familiar with Django/Flask, MySQL, and Redis, and has worked "
    "on two medium-sized projects."
)
DEFAULT_JD = (
    "Hiring a Python backend engineer with 3+ years of experience, "
    "familiar with microservices and database optimization."
)


@dataclass
class InterviewInputs:
    resume: str
    jd: str


def normalize_env_value(value: str | None) -> str:
    """Normalize values copied from .env files or terminals."""
    if not value:
        return ""
    return value.strip().strip('"').strip("'").strip()


def mask_secret(value: str) -> str:
    if len(value) <= 10:
        return f"<len={len(value)}>"
    return f"{value[:6]}...{value[-4:]} (len={len(value)})"


def is_auth_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "authenticationerror",
            "invalid_api_key",
            "incorrect api key",
            "error code: 401",
        )
    )


def run_local_demo(reason: str = "离线模式") -> None:
    print(f"Local demo mode: {reason}")
    print("=== Resume Analysis ===")
    print("Strengths: Python experience matches JD; Django/Flask, MySQL, and Redis are relevant.")
    print("Gaps: Microservices and database optimization experience need deeper validation.")
    print("\n=== Interview Transcript ===")
    print("8轮结构化面试对话模拟已生成。")
    print("\n=== Final Evaluation ===")
    print("Python: 7/10 | Database: 6/10 | Recommendation: Proceed to next round")


def build_dashscope_llm(api_key: str, base_url: str):
    from crewai import LLM

    return LLM(
        model="dashscope/qwen-plus",
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
    )


def run_ai_interviewer() -> None:
    if normalize_env_value(os.getenv("AI_INTERVIEWER_MODE")).lower() == "local":
        print("Demo演示\n")
        run_local_demo("AI_INTERVIEWER_MODE=local")
        return

    try:
        from crewai import Agent, Task, Crew, Process
    except ImportError as e:
        run_local_demo(f"缺少依赖: {e}")
        return

    api_key = normalize_env_value(os.getenv("DASHSCOPE_API_KEY"))
    if not api_key:
        run_local_demo("DASHSCOPE_API_KEY 为空")
        return

    base_url = normalize_env_value(os.getenv("DASHSCOPE_BASE_URL")) or DEFAULT_DASHSCOPE_BASE_URL
    os.environ["DASHSCOPE_API_KEY"] = api_key
    os.environ["DASHSCOPE_BASE_URL"] = base_url

    print("使用 CrewAI 官方 LLM + dashscope/qwen-plus 启动...")
    print(f"DashScope key loaded: {mask_secret(api_key)}")
    print(f"DashScope base URL: {base_url}")

    llm = build_dashscope_llm(api_key=api_key, base_url=base_url)

    resume_analyzer = Agent(
        role="专业简历分析师",
        goal="深入分析候选人简历和职位JD，找出匹配点、不足和面试重点。",
        backstory="你是拥有10年HR和技术招聘经验的资深专家。",
        verbose=True,
        llm=llm,
        allow_delegation=False,
        max_retry_limit=0,
    )

    interviewer = Agent(
        role="资深技术面试官",
        goal="主持多轮结构化面试，动态追问，考察候选人的真实能力。",
        backstory="你是大厂资深面试官，擅长根据简历生成针对性问题并实时跟进。",
        verbose=True,
        llm=llm,
        allow_delegation=False,
        max_retry_limit=0,
    )

    evaluator = Agent(
        role="客观评估专家",
        goal="根据完整面试过程给出结构化评分、反馈和最终报告。",
        backstory="你是中立严谨的评估专家，参考一线大厂标准打分。",
        verbose=True,
        llm=llm,
        allow_delegation=False,
        max_retry_limit=0,
    )

    task1 = Task(
        description=(
            "分析以下简历和职位描述：\n"
            "简历内容: {resume}\n"
            "职位JD: {jd}\n"
            "输出详细分析报告，包括优势、不足、建议重点考察方向。"
        ),
        expected_output="简历分析报告，使用 Markdown 格式。",
        agent=resume_analyzer,
    )

    task2 = Task(
        description=(
            "基于简历分析结果，主持一场完整的结构化技术面试，至少8-10轮对话。"
            "你可以假设候选人回答，并动态追问。"
        ),
        expected_output="完整的面试对话记录和关键能力评估。",
        agent=interviewer,
    )

    task3 = Task(
        description=(
            "根据完整面试过程，给出最终评估报告，包括各维度评分（1-10分）、"
            "整体推荐等级和改进建议。"
        ),
        expected_output="结构化的最终面试评估报告，使用 Markdown 格式。",
        agent=evaluator,
    )

    crew = Crew(
        agents=[resume_analyzer, interviewer, evaluator],
        tasks=[task1, task2, task3],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )

    inputs = InterviewInputs(resume=DEFAULT_RESUME, jd=DEFAULT_JD)
    try:
        result = crew.kickoff(inputs={"resume": inputs.resume, "jd": inputs.jd})
    except Exception as e:
        if is_auth_error(e):
            print("\nDashScope authentication failed.")
            print("请确认 DASHSCOPE_API_KEY 是阿里云百炼/Model Studio 的 DashScope API Key。")
            print(f"当前 endpoint: {base_url}")
            print(f"国内站 endpoint: {DEFAULT_DASHSCOPE_BASE_URL}")
            print("国际站 key 可在 .env 中设置:")
            print("DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
            run_local_demo("DashScope API Key 认证失败")
            return
        raise

    print("\n=== 最终评估报告 ===\n")
    print(result)


if __name__ == "__main__":
    print("AI面试官Agent启动中...\n")
    run_ai_interviewer()
