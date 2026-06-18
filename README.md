# AI Interviewer Agent

一个基于多 Agent 架构的 AI 智能面试系统，支持文字面试和视频面试两种模式。系统集成了 RAG 知识库增强、ToolCallGuard 循环保护、实时语音合成（TTS）和语音识别（STT），可自动完成多轮结构化面试并生成综合评估报告。

## 功能特性

- **多轮结构化面试**：可配置面试轮数，AI 面试官自动提问、追问、评估
- **两种面试模式**：文字面试（WebSocket）和视频面试（Socket.IO + Canvas 虚拟人）
- **RAG 知识增强**：题库检索、简历深挖、技术知识库、历史评估参考
- **ToolCallGuard**：防止 Agent 陷入无限循环，支持降级和负样本回流
- **实时语音**：Edge TTS 神经语音合成 + Google STT 语音识别
- **综合评估报告**：6 维度评分 + 录用建议，支持 JSON / CSV / HTML 导出
- **管理后台**：创建面试、查看面试列表、面试详情、Guard 日志、RAG 状态

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 实时通信 | python-socketio (Socket.IO) + WebSocket |
| AI 框架 | LangChain + LangGraph |
| LLM | OpenAI 兼容 API（支持 SiliconFlow / DeepSeek / 本地 Ollama 等） |
| 数据库 | SQLite + SQLAlchemy (Async) |
| 语音合成 | edge-tts (微软神经语音) |
| 语音识别 | Google STT / 浏览器 Web Speech API |
| 前端 | 原生 HTML/CSS/JS + Canvas 虚拟人 + Socket.IO Client |

## 项目结构

```
AIInterview/
├── app/
│   ├── agents/           # AI Agent 层
│   │   ├── interviewer.py   # 面试官 Agent - 生成面试问题
│   │   ├── evaluator.py     # 评估 Agent - 实时评估和最终评估
│   │   ├── coordinator.py   # 协调器 - LangGraph 工作流编排
│   │   ├── guard.py         # ToolCallGuard - 循环保护和降级
│   │   └── state.py         # LangGraph 状态定义
│   ├── api/              # API 路由
│   │   ├── admin.py         # 管理后台 API
│   │   ├── interview_ws.py  # WebSocket 面试处理器
│   │   ├── tts.py           # 语音合成 API (edge-tts)
│   │   └── stt.py           # 语音识别 API (Google STT)
│   ├── core/             # 核心配置
│   │   ├── config.py        # 应用配置
│   │   ├── database.py      # 数据库初始化
│   │   └── cache.py         # LLM 响应缓存
│   ├── data/             # 静态数据
│   │   ├── rag/             # RAG 知识库 (题库/知识/评估参考)
│   │   └── job_templates.json
│   ├── models/           # 数据模型
│   │   └── models.py        # SQLAlchemy ORM 模型
│   ├── rag/              # RAG 检索层
│   │   ├── manager.py       # RAG 管理器
│   │   ├── retrievers.py    # 各类检索器
│   │   └── vectorstore.py   # 向量存储
│   ├── realtime/         # 实时通信
│   │   └── socketio_server.py  # Socket.IO 面试服务器
│   ├── services/         # 业务逻辑层
│   │   ├── interview_service.py  # 面试业务逻辑
│   │   ├── email_service.py      # 邮件邀请服务
│   │   └── export_service.py     # 导出服务 (JSON/CSV/HTML)
│   ├── static/           # 前端静态资源
│   │   ├── css/             # 样式文件
│   │   ├── js/              # JavaScript 文件
│   │   └── images/          # 图片资源
│   └── templates/        # HTML 模板
│       ├── admin.html         # 管理后台
│       ├── interview.html     # 文字面试页
│       ├── video_interview.html # 视频面试页
│       ├── live_interview.html  # 实时面试页
│       └── result.html        # 面试结果页
├── tests/                # 单元测试
├── main.py               # FastAPI 应用入口
├── run.py                # 启动脚本
├── requirements.txt      # Python 依赖
└── .env.example          # 环境变量示例
```

## 快速开始

### 1. 环境要求

- Python 3.9+
- 支持 OpenAI 兼容 API 的 LLM 服务（如 SiliconFlow、DeepSeek、OpenAI 等）

### 2. 安装

```bash
# 克隆项目
git clone git@github.com:NongFuShangQuan/ai-interviewer-agent.git
cd ai-interviewer-agent

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# 必填：LLM API 配置
LLM_API_KEY=your-api-key-here
LLM_API_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct

# 服务器配置
HOST=0.0.0.0
PORT=9000

# 数据库（默认 SQLite）
DATABASE_URL=sqlite+aiosqlite:///./ai_interview.db

# 邮件配置（可选）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# 面试默认轮数
INTERVIEW_ROUNDS=5
```

**支持的 LLM 服务商：**

| 服务商 | LLM_API_BASE_URL | LLM_MODEL 示例 |
|--------|------------------|----------------|
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| 小米 MiMo | `https://token-plan-cn.xiaomimimo.com/v1` | `mimo-v2.5-pro` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

### 4. 启动

```bash
python run.py
```

服务启动后访问：
- 管理后台：http://localhost:9000/
- API 文档：http://localhost:9000/docs

### 5. 使用流程

1. 打开管理后台，点击「创建面试」
2. 填写候选人信息（姓名、邮箱、职位、简历等）
3. 系统生成面试链接并发送邀请邮件（需配置 SMTP）
4. 候选人打开面试链接开始面试
5. 面试完成后查看评估报告

**面试链接格式：**
- 文字面试：`http://localhost:9000/interview/{token}`
- 视频面试：`http://localhost:9000/video/{token}`
- 实时面试：`http://localhost:9000/live/{token}`

## 架构设计

### 多 Agent 工作流

```
管理员创建面试 → Socket.IO 连接 → 面试循环开始
                                      ↓
                              ┌──────────────────┐
                              │  Interviewer Agent │ ← RAG 题库 + 简历深挖
                              │  生成面试问题      │
                              └────────┬─────────┘
                                       ↓
                              ToolCallGuard 检查
                              (循环检测/降级/阻断)
                                       ↓
                              ┌──────────────────┐
                              │  候选人回答        │ ← 文字输入 / 语音识别
                              └────────┬─────────┘
                                       ↓
                              ┌──────────────────┐
                              │  Evaluator Agent   │ ← 实时评估
                              │  评估本轮回答      │
                              └────────┬─────────┘
                                       ↓
                              继续下一轮 or 结束
                                       ↓
                              ┌──────────────────┐
                              │  Final Evaluation │ ← 综合评估报告
                              │  6维度评分+建议   │
                              └──────────────────┘
```

### ToolCallGuard 保护机制

- **迭代限制**：每轮最多 8 次 Agent 调用，总共最多 150 次
- **循环检测**：滑动窗口指纹检测重复调用模式
- **降级策略**：检测到异常时自动回退到预设问题/默认评分
- **负样本回流**：循环事件记录为训练负样本，可用于 SFT/RL

## 测试

```bash
# 运行单元测试
pytest tests/

# 运行特定测试
pytest tests/test_evaluator.py
pytest tests/test_guard.py
pytest tests/test_rag.py
```
<img width="2547" height="700" alt="c35f0ad2-ffb2-44ca-a5d2-9f8867fbdb91" src="https://github.com/user-attachments/assets/5e67fcd3-5afc-4057-b664-fd571125a799" />
<img width="2560" height="942" alt="e482cc5f-90ff-4c4d-9fd9-2cf02d3335c8" src="https://github.com/user-attachments/assets/398fc653-1eb7-4733-9f8a-040c0039a9e8" />
<img width="1877" height="891" alt="c2e40e6e-75ed-46dd-a041-486e63a45b07" src="https://github.com/user-attachments/assets/90f99290-97bf-4a3c-9196-278a5691a63c" />
<img width="1908" height="879" alt="8dac7781-3e02-4e28-a98d-5874b85f95e0" src="https://github.com/user-attachments/assets/49517b7f-f896-4b2c-a597-a4b8a745fb02" />


## 许可证

MIT License
