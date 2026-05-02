# ai-interviewer-agent

基于 CrewAI 的多 Agent AI 智能面试官系统（北森风格数字人版）

## 项目亮点
- **多 Agent 协作**：简历分析 + 结构化面试 + 自动评估闭环
- **北森风格数字人**：实时眼球跟随 + 嘴巴说话动画 + Streamlit 可视化界面
- **技术栈**：CrewAI + 通义千问（Qwen） + Streamlit+.....

## 项目结构

```bash
ai-interviewer-agent/
├── Agent/                          # 1. Agent 核心层（多Agent协作 + 长链推理）
│   ├── __init__.py
│   ├── ai_interviewer.py           # 主程序（3个Agent + Crew）
│   ├── resume_analyzer.py
│   ├── interviewer.py
│   └── evaluator.py
├── digital_human/                  # 2. 数字人展示层（视觉 + 眼球算法）
│   ├── __init__.py
│   ├── streamlit_app.py            # Streamlit 可视化界面（北森风格数字人）
│   └── avatar.png                  # 数字人图片
├── backend/                        # 3. 后端业务层（可选，后续扩展）
│   ├── __init__.py
│   ├── main.py                     # FastAPI 主程序
│   └── ...
├── .env
├── requirements.txt
├── README.md
├── run_agent_only.py               # 快速测试 Agent
└── run_streamlit.bat               # 一键启动数字人界面（可选）
