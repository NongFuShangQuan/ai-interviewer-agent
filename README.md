# AI Interviewer Agent

基于 LangGraph 多 Agent 协作的 AI 智能面试官系统，支持文本/视频/实时语音三种面试模式，集成 RAG 检索增强、数字人交互、六维评估报告等能力。

## 功能特性

- **多 Agent 协作** — LangGraph 编排面试官、评估官、协调器三个 Agent，自动完成提问-评估-追问闭环
- **三种面试模式** — 文本聊天、视频数字人、实时语音面试，覆盖不同场景需求
- **RAG 检索增强** — 题库检索、简历深挖、评估参考、岗位知识四路召回，提升问答质量
- **六维评估报告** — 技术能力、沟通表达、问题解决、文化匹配、经验匹配、综合评分，自动生成录用建议
- **数字人交互** — Canvas 渲染虚拟形象，支持呼吸/眨眼/嘴型动画 + 摄像头眼球追踪
- **语音能力** — Edge TTS 神经语音合成 + Google STT 语音识别，支持多种中文音色
- **管理后台** — SPA 仪表盘，面试创建/记录查看/系统监控/RAG 知识库管理/数据导出
- **安全防护** — ToolCallGuard 工具调用守卫，循环检测、迭代限制、快速熔断、降级兜底

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn + python-socketio |
| AI 编排 | LangChain + LangGraph + ChatOpenAI |
| 数据库 | SQLAlchemy (async) + aiosqlite (SQLite) |
| 语音 | edge-tts (TTS) + speech_recognition (STT) |
| 前端 | Jinja2 模板 + 原生 JS + Socket.IO |
| 配置 | Pydantic Settings + .env |

支持多种 LLM 提供商：SiliconFlow（默认）、OpenAI、DeepSeek、本地 Ollama。未配置 API Key 时自动降级为 Mock 模式。

## 项目结构

```
AIInterview/
├── main.py                         # FastAPI 入口 + Socket.IO ASGI 挂载
├── run.py                          # 启动脚本
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
│
├── app/
│   ├── agents/                     # LangGraph 多 Agent 系统
│   │   ├── coordinator.py          #   协调器：StateGraph 工作流编排
│   │   ├── interviewer.py          #   面试官 Agent：题目生成 + RAG
│   │   ├── evaluator.py            #   评估官 Agent：轮次评分 + 终面评估
│   │   ├── guard.py                #   ToolCallGuard：循环检测 + 降级引擎
│   │   └── state.py                #   状态定义：InterviewState + EvaluationResult
│   │
│   ├── api/                        # API 路由
│   │   ├── admin.py                #   管理后台 CRUD、Guard 统计、RAG、导出
│   │   ├── tts.py                  #   文本转语音 API（Edge TTS）
│   │   └── stt.py                  #   语音转文字 API（Google STT）
│   │
│   ├── core/                       # 基础设施
│   │   ├── config.py               #   Pydantic Settings 环境配置
│   │   ├── database.py             #   SQLAlchemy 异步引擎 + 会话工厂
│   │   └── cache.py                #   LLM 响应缓存（LRU + TTL + 磁盘持久化）
│   │
│   ├── data/                       # 静态数据
│   │   ├── job_templates.json      #   岗位模板（技术/产品/设计/运营/市场/HR）
│   │   └── rag/                    #   RAG 数据存储
│   │       └── question_bank.json  #     40+ 面试题（覆盖 12 个技术方向）
│   │
│   ├── models/models.py            # ORM 模型（6 张表）
│   ├── rag/                        # RAG 检索增强系统
│   │   ├── manager.py              #   统一管理器单例
│   │   ├── retrievers.py           #   4 个检索器：题库/简历/评估参考/知识库
│   │   └── vectorstore.py          #   混合向量存储（Embedding API + TF-IDF 降级）
│   │
│   ├── realtime/socketio_server.py # Socket.IO 实时通信服务
│   ├── services/                   # 业务服务
│   │   ├── interview_service.py    #   面试 CRUD
│   │   ├── email_service.py        #   SMTP 邀请邮件
│   │   └── export_service.py       #   导出 JSON/CSV/HTML
│   │
│   ├── static/                     # 前端资源
│   │   ├── css/                    #   样式
│   │   ├── js/                     #   脚本（admin/interview/video/live/particles）
│   │   └── images/digital_human/   #   数字人素材（idle/speaking/listening/thinking）
│   │
│   └── templates/                  # HTML 模板
│       ├── admin.html              #   管理后台（SPA）
│       ├── interview.html          #   文本面试
│       ├── video_interview.html    #   视频面试（Canvas 数字人）
│       ├── live_interview.html     #   实时语音面试
│       └── result.html             #   结果页
│
└── tests/                          # 单元测试
    ├── test_guard.py               #   Guard 系统测试
    ├── test_evaluator.py           #   JSON 提取测试
    ├── test_models.py              #   模型结构测试
    ├── test_rag.py                 #   TF-IDF + Embedding 测试
    └── test_state.py               #   状态定义测试
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 LLM API Key：

```env
LLM_API_KEY=your-api-key-here
LLM_API_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=mimo-v2-omni
```

### 3. 启动服务

```bash
python run.py
```

服务默认运行在 `http://localhost:9000`，访问 `/` 进入管理后台。

## 环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | （必填） | LLM 服务 API Key |
| `LLM_API_BASE_URL` | `https://api.siliconflow.cn/v1` | LLM API 地址 |
| `LLM_MODEL` | `mimo-v2-omni` | 模型名称 |
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `9000` | 服务端口 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./ai_interview.db` | 数据库连接 |
| `SMTP_HOST` | `smtp.gmail.com` | 邮件服务器 |
| `SMTP_PORT` | `587` | 邮件端口 |
| `SMTP_USER` | （空） | 邮箱用户名 |
| `SMTP_PASSWORD` | （空） | 邮箱密码 |
| `INTERVIEW_ROUNDS` | `10` | 默认面试轮数 |

## 使用流程

1. 访问 `/` 打开管理后台
2. 点击「创建面试」，选择岗位模板、填写候选人信息、选择面试类型
3. 系统生成面试链接，可通过邮件发送给候选人
4. 候选人打开链接开始面试（文本/视频/语音）
5. 面试结束后，系统自动生成六维评估报告
6. 在管理后台查看结果，支持 JSON/CSV/HTML 导出

## 多 Agent 架构

```
候选人回答
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ Interviewer │────▶│  Evaluator  │────▶│ Final Evaluation│
│  面试官 Agent│     │  评估官 Agent│     │   终面评估       │
└──────┬──────┘     └──────┬──────┘     └─────────────────┘
       │                   │
       │   RAG 检索增强     │
       ▼                   ▼
┌──────────────────────────────────┐
│          RAG Manager             │
│  题库 │ 简历 │ 评估参考 │ 知识库  │
└──────────────────────────────────┘
```

- **面试官 Agent** — 结合 RAG 检索结果生成面试题目，30 秒超时自动降级
- **评估官 Agent** — 轮次评分（1-10 分）+ 终面六维评估，支持 JSON 容错解析
- **协调器** — LangGraph StateGraph 编排工作流，在问答之间暂停等待外部输入
- **ToolCallGuard** — 滑动窗口指纹检测、迭代限制、快速熔断、降级兜底，防止 Agent 死循环

## 运行测试

```bash
python -m pytest tests/
```

## License

MIT
