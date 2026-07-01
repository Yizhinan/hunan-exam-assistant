# 湖南公务员考试助手

面向湖南公务员考试的 AI 智能备考助手。首期功能：**申论 AI 批改**。

## 架构

```
React 18 + TypeScript + TailwindCSS    → 前端
FastAPI + Python 3.12                  → 后端
DeepSeek V4 Pro                        → LLM 批改引擎
PostgreSQL 16                          → 结构化存储
ChromaDB                               → 向量知识库 (RAG)
Scrapy + Playwright                    → 真题/时政爬虫
Celery + Redis                         → 异步任务/定时调度
Docker Compose                         → 一键部署
```

## 快速开始

### 前置条件

- Docker Desktop
- DeepSeek API Key ([获取地址](https://platform.deepseek.com))

### 启动

```bash
# 1. 设置 API Key
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY

# 2. 启动所有服务
docker-compose up -d

# 3. 访问
# 前端: http://localhost:5173
# 后端 API 文档: http://localhost:8000/docs
```

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

## API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/auth/register` | 用户注册 |
| `POST /api/auth/login` | 用户登录 |
| `GET /api/auth/me` | 获取当前用户信息 |
| `POST /api/essay/grade` | 提交申论批改 ★ |
| `GET /api/essay/history` | 批改历史 |
| `GET /api/essay/{id}` | 批改详情 |
| `POST /api/knowledge/upload` | 上传文档到知识库 |
| `GET /api/knowledge/search` | 知识库语义检索 |
| `GET /api/knowledge/documents` | 知识库文档列表 |

## 申论批改评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 立意观点 | 25% | 切题程度、立场正确性、观点深度 |
| 结构逻辑 | 20% | 层次清晰度、论证严密性 |
| 内容论据 | 25% | 论据充分度、湖南实际结合度 |
| 语言表达 | 20% | 规范性、流畅度 |
| 格式规范 | 10% | 文体格式、字数控制 |

## 项目结构

```
hunan-exam-assistant/
├── frontend/          # React 前端
│   └── src/
│       ├── pages/
│       │   ├── Auth/           # 登录/注册
│       │   ├── EssayGrading/   # 申论批改（提交/结果/历史）
│       │   └── Admin/          # 管理后台
│       ├── components/layout/  # 布局组件
│       ├── hooks/              # React Hooks (useAuth)
│       └── services/           # API 客户端
├── backend/           # FastAPI 后端
│   └── app/
│       ├── api/                # API 路由 (auth/essay/knowledge)
│       ├── core/               # 核心引擎 (批改/RAG/LLM/配置)
│       ├── models/             # ORM 模型
│       ├── crawlers/           # 爬虫业务逻辑
│       └── tasks/              # Celery 异步任务
├── crawler/           # Scrapy 爬虫项目
│   └── hunan_exam/spiders/    # 真题爬虫 + 时政爬虫
└── docker-compose.yml # 容器编排
```

## 爬虫

```bash
# 手动运行
cd crawler
scrapy crawl hunan_gov      # 湖南省政府时政
scrapy crawl rednet         # 红网新闻
scrapy crawl offcn_exam     # 中公真题
scrapy crawl huatu_exam     # 华图真题
```
