# 🤖 AI Semantic Layer Agent — P-069

> **Dự án thuộc VinUni AI20K Build Phase (Cohort 3)**  
> **Nền tảng AI Agent hỗ trợ xây dựng, quản trị lớp ngữ nghĩa dữ liệu (Semantic Layer) tập trung & biên dịch truy vấn dữ liệu kinh doanh chuẩn xác.**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Next.js-14.2+-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6F61?style=flat)](https://langchain-ai.github.io/langgraph/)
[![SQLGlot](https://img.shields.io/badge/sqlglot-25.0+-blue?style=flat)](https://github.com/tobymao/sqlglot)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Tổng quan bài toán (Problem Statement)

Trong các doanh nghiệp hiện nay, dữ liệu lưu trữ tại cơ sở dữ liệu quan hệ (PostgreSQL, MySQL, SQLite) thường đối mặt với **2 thách thức lớn**:

1. **Khoảng cách Ngữ cảnh Nghiệp vụ (Business Context Gap):** Tên bảng và cột mang tính kỹ thuật khô khan (`usr_tbl_01`, `amt_vat_inc`, `ord_sts_cd`), khiến người dùng nghiệp vụ hoặc BA/DA mất nhiều thời gian tra cứu từ điển dữ liệu (Data Dictionary), dễ gây hiểu sai bản chất số liệu.
2. **Hỗn loạn Định nghĩa Chỉ số (Metric Definition Chaos):** Thiếu một "nguồn sự thật duy nhất" (Single Source of Truth) cho các công thức tính chỉ số cốt lõi (doanh thu thuần, tỷ lệ chuyển đổi, ARPU...). Mỗi phòng ban tự tính toán theo logic riêng dẫn đến báo cáo không thống nhất.

### 💡 Giải pháp: AI Semantic Layer Agent (v1.0)

**AI Semantic Layer Agent** tự động hóa quy trình **Introspect Schema → AI Đặt tên Nghiệp vụ tiếng Việt & Đề xuất Chỉ số → HITL Review (Người dùng phê duyệt) → Lưu vào Metadata Store → Export JSON/YAML** để tích hợp với các công cụ BI.

---

## 🎯 Phạm vi dự án (Project Scope)

### ✅ In-Scope (v1.0 - Flow 1 Pipeline)

- **Schema Introspection:** Tự động đọc metadata (tables, columns, foreign keys, data types) qua `SQLAlchemy Inspector`. **Tuyệt đối không query/SELECT data** trên Target DB.
- **AI Business Enrichment:** Dùng LLM (GPT-4o-mini) chuyển đổi tên kỹ thuật sang tên nghiệp vụ chuẩn Tiếng Việt và viết mô tả chi tiết.
- **Metric Suggestion:** LLM phân tích schema để gợi ý Business Metrics kèm câu lệnh SQL template.
- **HITL (Human-In-The-Loop) Review:** Giao diện phê duyệt/chỉnh sửa trực tiếp trước khi lưu.
- **Security:** Mã hóa đối xứng Fernet đối với Connection URL (không lưu plaintext).
- **Metadata Management & Export:** Thêm/sửa/xóa Business Metrics thủ công và xuất Semantic Layer ra chuẩn **JSON** và **YAML**.

### ❌ Out-of-Scope (v1.0)

- Không thực thi câu lệnh SQL SELECT trên Target DB.
- Không hỗ trợ NL2SQL Chatbot / Natural Language Query (dành cho v2.0+).
- Không dùng Vector Database (ChromaDB, FAISS).

---

## 🏗 Kiến trúc Hệ thống (System Architecture)

```mermaid
graph TB
    subgraph Client["🖥️ Client Layer — Next.js 14 Web App"]
        V1["📊 Data Model View"]
        V2["📋 Metrics Catalog View"]
        V3["🔍 Metric Explorer View"]
        V4["💬 AI Studio View"]
        V5["📤 Export Playground View"]
    end

    subgraph API["🌐 API Layer — FastAPI Async Gateway"]
        A1["🔐 Auth & RBAC (/api/v1/auth)"]
        A2["📥 Ingestion & Live DB Connect (/api/v1/semantic/...)"]
        A3["📚 Catalog & Metadata CRUD (/api/v1/semantic/{db_id}/...)"]
        A4["⚡ Semantic Query Engine (/api/v1/semantic/{db_id}/query)"]
        A5["🤖 Multi-Agent Studio & Clarifier (/api/v1/semantic/{db_id}/...)"]
    end

    subgraph Pipelines["⚙️ Core Processing Engines"]
        P_F1["Flow 1: Ingestion -> Pass 1 Glossary -> Clustering -> Pass 2 Enrichment -> Canonical Builder -> HITL"]
        P_F2["Flow 2: Resolver -> SemanticQueryCompiler -> sqlglot Guardrails (LIMIT 100) -> Live DB Execution"]
        P_AG["Conversational: Chat Orchestrator Graph & Query Clarifier Wizard Graph"]
    end

    subgraph Storage["🗄️ Storage Layer"]
        METADB[("🗄️ Metadata Store (PostgreSQL / SQLite)\n10 ORM Tables")]
        TARGET[("🎯 Target DB (Live DB Read-Only)\nPostgreSQL / MySQL / SQLite")]
    end

    Client --> API
    API --> Pipelines
    Pipelines --> Storage
```

---

## 📁 Cấu trúc Thư mục Dự án

```
P-069/
├── src/
│   ├── agents/                   # 🧠 Hệ thống Agent LangGraph & Multi-Agent
│   │   ├── nodes/                #    Các node: introspect, enrich, metric_suggest, chitchat, orchestrator, save
│   │   ├── query_clarifier/      #    Query Clarifier Wizard (wizard_init, wizard_step, resolve)
│   │   ├── graph.py              #    StateGraph Flow 1 chính với HITL interrupt
│   │   ├── chat_graph.py         #    StateGraph hội thoại đa tác tử
│   │   └── state.py              #    AgentState TypedDict
│   ├── api/                      # 🌐 FastAPI REST API Routes
│   │   ├── auth.py               #    Xác thực JWT, Bcrypt, Google OAuth, Refresh token, RBAC
│   │   ├── query_clarify_routes.py # API endpoints cho Query Clarifier Wizard
│   │   └── routes.py             #    Tập trung 25+ API endpoints của hệ thống
│   ├── models/                   # 📋 SQLAlchemy ORM Models & Pydantic Schemas
│   │   ├── db.py                 #    10 ORM Models (users, sessions, imported_schemas, canonical_relationships...)
│   │   ├── metric_definition.py  #    MetricDefinition v2 schema & validator
│   │   ├── schema_metadata.py    #    RawSchemaMetadata & Diagnostic codes
│   │   └── schemas.py            #    Pydantic Request/Response models
│   ├── services/                 # 🔧 Core Services & Business Logic
│   │   ├── canonical_builder_service.py # Xây dựng canonical schema từ technical schema
│   │   ├── clustering.py         #    Phân cụm đồ thị bảng (Domain/Graph Clustering)
│   │   ├── pass1_global_glossary.py # Pass 1 Global Domain Glossary
│   │   ├── pass2_cluster_enrichment.py # Pass 2 Cluster Enrichment + Fallback
│   │   ├── query_compiler.py     #    Deterministic Semantic Query Compiler
│   │   ├── query_execution.py    #    Safe Live DB execution service
│   │   ├── sql_dump_scanner.py   #    SQL Dump DDL scanner
│   │   ├── sql_dump_parser.py    #    SQL Dump AST parser
│   │   ├── export_service.py     #    Xuất bản Semantic Layer ra JSON/YAML
│   │   ├── live_db_service.py    #    Quản lý kết nối Target Live DB
│   │   ├── imported_schema_service.py # Quản lý schema import từ file dump
│   │   ├── semantic_service.py   #    Quản lý Semantic Layer, Catalog, Versioning
│   │   ├── database.py           #    AsyncEngine & Fernet encryption
│   │   └── llm.py                #    Factory get_llm() (GPT-4o-mini, temp=0.0)
│   ├── config.py                 # ⚙️ Application Settings (Pydantic-settings)
│   └── main.py                   # 🚀 FastAPI App Entry Point & Lifespan
├── frontend/                     # 🖥️ Next.js 14 Single Page Workspace App
│   ├── src/
│   │   ├── app/                  #    App Router (Landing /, Semantic Workspace /semantic/[db_id])
│   │   ├── components/
│   │   │   ├── views/            #    5 Views: DataModel, MetricsCatalog, MetricExplorer, AIStudio, Export
│   │   │   ├── studio/           #    Streaming chat & SQL/YAML syntax highlighters
│   │   │   ├── explorer/         #    AI Query Assistant Modal & Wizard
│   │   │   └── modals/           #    Modals kết nối DB & Upload SQL Dump
│   │   ├── context/              #    Global State Context (Auth, Workspace, Schema)
│   │   └── lib/                  #    API client & utility helpers
│   ├── package.json              #    Frontend dependencies
│   └── tailwind.config.ts        #    Tailwind CSS styling configuration
├── alembic/                      # 🗄️ Database Migrations (Alembic)
│   ├── versions/                 #    Lịch sử các bản migration
│   └── env.py                    #    Cấu hình AsyncEngine migration
├── data/                         # 💾 Dữ liệu mẫu & SQL benchmark
├── docs/                         # 📚 Tài liệu chi tiết dự án
│   ├── BRIEF.md                  #    Tóm tắt dự án
│   ├── PRD.md                    #    Product Requirements Document
│   ├── DATABASE_DESIGN.md        #    Thiết kế CSDL & ERD 10 bảng (v2.0)
│   ├── FEATURE_SPECIFICATIONS.md #    Đặc tả chi tiết các tính năng chính
│   ├── UI_FLOW.md                #    Luồng màn hình & Wireframes
│   └── ACTION_PLAN.md            #    Kế hoạch hành động & Tiến độ
├── scripts/                      # 🔌 Utility & Database Setup Scripts
│   ├── setup_target_db.py        #    Khởi tạo Golden Retail Benchmark DB
│   └── setup_hooks.ps1           #    Setup AI usage logging hooks
├── tests/                        # 🧪 Test Suite (pytest)
│   ├── test_agents/              #    Tests cho LangGraph nodes & Chat/Wizard graphs
│   ├── test_api/                 #    Integration tests cho 25+ API endpoints
│   ├── test_models/              #    Unit tests cho ORM models & Pydantic schemas
│   └── test_services/            #    Unit tests cho 2-Pass, Compiler, Dump Scanner, Auth...
├── ARCHITECTURE.md               # 🏛 Architecture Document chi tiết
├── AGENTS.md                     # 📜 Quy tắc phát triển & AI Rules
├── docker-compose.dev.yml        # 🐳 Docker Compose môi trường Development
├── docker-compose.yml            # 🐙 Docker Compose môi trường Production
├── Dockerfile                    # 🐳 Dockerfile Backend
├── requirements.txt              # 📦 Python Dependencies
└── README.md                     # 📖 Tài liệu hướng dẫn (File này)
```

---

## ⚡ Quick Start & Hướng dẫn cài đặt

### 1. Yêu cầu tiên quyết

- **Python:** `3.11+`
- **Node.js:** `18+` & `npm` / `pnpm`
- **Docker & Docker Compose** (khuyên dùng Docker Desktop trên Windows/macOS)
- **Git**

---

### 2. Cài đặt Backend (FastAPI)

```bash
# 1. Clone repository
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-069.git
cd P-069

# 2. Tạo & kích hoạt virtualenv
python -m venv .venv

# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
# source .venv/bin/activate

# 3. Cài đặt dependencies backend
pip install -r requirements.txt
```

---

### 3. Cài đặt Frontend (Next.js 14 Web App)

```bash
# Chuyển vào thư mục frontend và cài đặt node_modules
cd frontend
npm install
cd ..
```

---

### 4. Cấu hình Biến môi trường (`.env`)

Sao chép `.env.example` thành `.env` tại thư mục gốc:

```bash
cp .env.example .env
```

#### 📋 Bảng Chi tiết Biến Môi trường (Environment Variables Reference)

| Nhóm | Tên biến | Kiểu / Giá trị mẫu | Bắt buộc | Mô tả chi tiết |
| --- | --- | --- | --- | --- |
| **App Core** | `APP_ENV` | `development` / `production` | Không (Mặc định: `development`) | Môi trường thực thi của hệ thống |
| | `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Không (Mặc định: `INFO`) | Mức độ chi tiết log hệ thống |
| | `APP_PORT` | `8000` | Không (Mặc định: `8000`) | Cổng lắng nghe của FastAPI Backend |
| | `APP_HOST` | `0.0.0.0` | Không (Mặc định: `0.0.0.0`) | Địa chỉ IP host backend lắng nghe |
| | `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Không | Danh sách domain client được phép gọi API |
| | `SECRET_KEY` | `your-secret-key-32-chars-minimum` | **Có (khi chạy prod)** | Khóa bí mật ký JWT Token (Access & Refresh) |
| **Security** | `ENCRYPTION_KEY` | `Fernet Base64 Key` | **Có** | Khóa mã hóa đối xứng Fernet dùng để mã hóa chuỗi kết nối Target DB |
| **Database** | `DATABASE_URL` | `postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev` | **Có** | Connection string Metadata Store (PostgreSQL AsyncPG) |
| | `TARGET_DATABASE_URL` | `postgresql://dev:devpassword@localhost:5432/ecommerce_db` | Không | Connection string dùng cho script tạo Live Target DB mẫu |
| **LLM Provider** | `LLM_PROVIDER` | `openai` \| `gemini` \| `groq` \| `mimo` \| `anthropic` \| `custom` | Không (Mặc định: `openai`) | Lựa chọn nhà cung cấp mô hình ngôn ngữ lớn |
| | `OPENAI_API_KEY` | `sk-proj-...` | **Có (nếu LLM=openai)** | Khóa API của OpenAI |
| | `GOOGLE_API_KEY` | `AIzaSy...` | Tùy chọn (nếu LLM=gemini) | Khóa API Google AI Studio |
| | `GROQ_API_KEY` | `gsk_...` | Tùy chọn (nếu LLM=groq) | Khóa API Groq Cloud (Tốc độ phản hồi cực nhanh) |
| | `MIMO_API_KEY` | `your-mimo-key` | Tùy chọn (nếu LLM=mimo) | Khóa API Xiaomi MiMo |
| | `ANTHROPIC_API_KEY` | `sk-ant-...` | Tùy chọn (nếu LLM=anthropic) | Khóa API Anthropic Claude |
| | `MODEL_NAME` | `gpt-4o-mini`, `gemini-1.5-flash`, `llama-3.3-70b-versatile` | Không | Tên mô hình chính áp dụng toàn hệ thống |
| | `LLM_TEMPERATURE` | `0.0` | Không (Mặc định: `0.0`) | Độ ngẫu nhiên (Bắt buộc `0.0` cho tính nhất quán) |
| | `LLM_API_BASE` | `http://localhost:8000/v1` | Tùy chọn | Base URL cho endpoint OpenAI-compatible (vLLM, Ollama, proxy) |
| | `LLM_MODEL_ENRICH` | `llama-3.1-8b-instant` | Tùy chọn | Mô hình riêng cho bước Schema Enrichment |
| | `LLM_MODEL_METRIC` | `llama-3.3-70b-versatile` | Tùy chọn | Mô hình riêng cho bước Business Metric Suggestion |
| **Observability** | `LANGCHAIN_API_KEY` | `lsv2_pt_...` | Không | Khóa API LangSmith để theo dõi trace AI Agent |
| | `LANGCHAIN_PROJECT` | `ai20k-agent` | Không | Tên dự án trace trên LangSmith |
| | `LANGCHAIN_TRACING_V2` | `true` | Không | Bật chế độ trace chi tiết cho LangGraph |
| **AI Logging** | `AI_LOG_SERVER` | `https://ai-logs.note.transformerlabs.ai/api/ingest` | Không | Server thu thập log AI VinUni AI20K |
| | `AI_LOG_API_KEY` | `your-ai-log-api-key` | Không | Khóa API định danh học viên |
| **Frontend** | `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Không | URL Backend API mà Frontend gọi tới |

> [!TIP]
> **Cách sinh khóa Fernet nhanh bằng Python một dòng:**
>
> ```bash
> python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
> ```

---

### 5. Thiết lập AI Usage Logging Hooks (Dành cho Học viên VinUni AI20K)

```bash
# Trên Windows PowerShell:
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1

# Trên Linux / macOS / Git Bash:
bash scripts/setup_hooks.sh
```

---

## 🗄️ Khởi tạo, Quản trị & Seed Dữ liệu Cơ sở Dữ liệu (Database Setup & Seeding)

Hệ thống phân tách rành mạch **2 cơ sở dữ liệu**:

1. **Metadata Store (PostgreSQL):** Lưu thông tin người dùng, phiên làm việc, schema kỹ thuật, tên/mô tả nghiệp vụ tiếng Việt, Canonical Relationships, Business Metrics và lịch sử phiên bản (`metric_versions`).
2. **Target Live DB (Chỉ đọc & thực thi SELECT có trần):** DB dữ liệu kinh doanh của doanh nghiệp. Agent kết nối qua SQLAlchemy Inspector để đọc cấu trúc và thực thi các câu lệnh `SELECT` đã được biên dịch qua Flow 2.

---

### 1. Khởi tạo Metadata Store & Chạy Migrations

```bash
# 1. Khởi chạy PostgreSQL Metadata Store và PgWeb UI
docker compose -f docker-compose.dev.yml up postgres pgweb -d

# 2. Cập nhật Database Schema lên phiên bản mới nhất bằng Alembic
alembic upgrade head
```

- **PgWeb UI (Trình quản trị Web Database):** Truy cập tại [http://localhost:8081](http://localhost:8081) để xem trực quan các bảng của Metadata Store và Target DB.

---

### 2. Hướng dẫn Seed Database Mẫu (Target Database Seeding)

Dự án cung cấp sẵn nhiều phương thức nạp dữ liệu thử nghiệm phục vụ kiểm thử và demo:

#### 🔹 Phương án A: Seed Golden Retail Benchmark Database (36 Bảng, 5.000 Orders) — *Khuyên dùng*

Script tự động khởi tạo database `golden_retail_db` trên PostgreSQL, import 36 bảng chuẩn Enterprise Retail (`order_header`, `order_line`, `products`, `customers`, `stores`, `sales_channels`, `inventory`, `payments`...) kèm 8.5MB dữ liệu seed thực tế:

```bash
# Chạy script tự động seed dữ liệu
python scripts/setup_target_db.py
```

- **Chuỗi kết nối (Connection URL) để kết nối trên UI / API:**
  - Kết nối từ máy Host (Local): `postgresql://dev:devpassword@localhost:5432/golden_retail_db`
  - Kết nối từ trong mạng Docker: `postgresql://dev:devpassword@postgres:5432/golden_retail_db`

#### 🔹 Phương án B: Tự động Sinh lại Bộ Dữ liệu Mới (Custom Seed Data Generator)

Nếu muốn tạo mới hoặc tùy biến khối lượng dữ liệu từ đầu:

```bash
# 1. Sinh cấu trúc DDL và bộ dữ liệu giao dịch giả lập
python scripts/seed_data_generator.py

# 2. Chuyển đổi định dạng DDL/DML tương thích hoàn toàn PostgreSQL
python scripts/convert_to_postgres.py

# 3. Nạp lại vào database đích
python scripts/setup_target_db.py
```

---

## 🚀 Khởi chạy Ứng dụng

### Cách 1: Khởi chạy Cục bộ (Local Development — Khuyên dùng)

**Terminal 1 — Backend (FastAPI):**

```bash
# Đảm bảo virtualenv đã được kích hoạt
uvicorn src.main:app --reload --port 8000
```

- API Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- API ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

**Terminal 2 — Frontend (Next.js 14):**

```bash
cd frontend
npm run dev
```

- Web Application UI: [http://localhost:3000](http://localhost:3000)

---

### Cách 2: Khởi chạy Trọn gói qua Docker Compose

```bash
# Chạy toàn bộ hệ thống (PostgreSQL + Backend + Frontend + PgWeb)
docker compose -f docker-compose.dev.yml up --build -d

# Xem log thời gian thực của backend
docker compose -f docker-compose.dev.yml logs -f backend

# Dừng toàn bộ hệ thống
docker compose -f docker-compose.dev.yml down
```

---

## 🔗 Danh mục API Endpoints Đầy đủ (25+ Endpoints)

### 1. Xác thực & Quản lý Người dùng (Auth & RBAC)

- `POST /api/v1/auth/register` — Đăng ký tài khoản mới, cấp JWT Access + Refresh token
- `POST /api/v1/auth/login` — Đăng nhập bằng Email/Username & Mật khẩu
- `POST /api/v1/auth/google` — Đăng nhập / Đăng ký qua Google OAuth ID Token
- `POST /api/v1/auth/refresh` — Quay vòng Refresh Token (Token Rotation) & cấp cặp token mới
- `GET /api/v1/auth/me` — Lấy thông tin tài khoản người dùng hiện tại
- `POST /api/v1/auth/logout` — Thu hồi phiên đăng nhập (Revoke Refresh Token)

### 2. Tiếp nhận CSDL & Schema Ingestion (Flow 1)

- `POST /api/v1/semantic/import/preview` — Phân tích cú pháp file SQL Dump DDL (PostgreSQL, MySQL, SQLite) và trả về Technical Schema Preview + Diagnostics
- `POST /api/v1/semantic/import/saved` — Lưu cấu trúc SQL Dump đã parse vào Metadata Store
- `GET /api/v1/semantic/import/saved` — Danh sách các schema SQL Dump đã lưu
- `GET /api/v1/semantic/import/saved/{schema_id}` — Xem chi tiết schema SQL Dump
- `DELETE /api/v1/semantic/import/saved/{schema_id}` — Xóa schema SQL Dump
- `POST /api/v1/semantic/db/connect` — Kết nối Target Live DB, mã hóa Fernet URL, introspect schema và lưu Metadata
- `GET /api/v1/semantic/db/saved` — Danh sách các kết nối Live DB
- `GET /api/v1/semantic/db/saved/{db_id}` — Xem chi tiết kết nối Live DB
- `DELETE /api/v1/semantic/db/saved/{db_id}` — Xóa kết nối Live DB

### 3. Làm giàu Ngữ nghĩa & Phê duyệt HITL (Flow 1 Enrichment)

- `POST /api/v1/semantic/generate` — Chạy pipeline 2-Pass AI Schema Enrichment (Glossary $\rightarrow$ Clustering $\rightarrow$ Vietnamese Business Names & Metrics)
- `POST /api/v1/semantic/approve` — Phê duyệt toàn bộ Draft Metrics cho một Semantic Database
- `POST /api/v1/semantic/{db_id}/metric/{metric_id}/approve` — Phê duyệt một Business Metric cụ thể
- `PUT /api/v1/semantic/{db_id}/table/{table_name}` — Chỉnh sửa inline tên/mô tả nghiệp vụ của Bảng
- `PUT /api/v1/semantic/{db_id}/column/{table_name}/{column_name}` — Chỉnh sửa inline tên/mô tả nghiệp vụ của Cột

### 4. Quản trị Chỉ số Kinh doanh & Lịch sử Phiên bản (Business Metrics Catalog)

- `POST /api/v1/semantic/{db_id}/metrics/generate` — Sinh gợi ý Business Metrics thông minh từ Prompt tiếng Việt
- `POST /api/v1/semantic/{db_id}/metric` — Tạo mới Business Metric (AI hoặc thủ công) kèm phiên bản v1
- `GET /api/v1/semantic/{db_id}/metrics` — Danh sách Business Metrics kèm trạng thái và phiên bản
- `PUT /api/v1/semantic/{db_id}/metric/{metric_id}` — Cập nhật công thức Metric, tự động tăng phiên bản và lưu `metric_versions`
- `GET /api/v1/semantic/{db_id}/metric/{metric_id}/history` — Xem lịch sử thay đổi phiên bản của Metric
- `DELETE /api/v1/semantic/{db_id}/metric/{metric_id}` — Xóa Business Metric

### 5. Catalog & Xuất bản (Catalog & Export)

- `GET /api/v1/semantic/{db_id}/catalog` — Trả về danh mục Canonical Tables, Columns, Relationships và cờ hỗ trợ Live Query
- `GET /api/v1/semantic/{db_id}/export?format=json|yaml` — Tải xuống Semantic Layer đã duyệt theo định dạng JSON hoặc YAML

### 6. Động cơ Truy vấn Ngữ nghĩa & Guardrails (Flow 2 — Live DB Only)

- `POST /api/v1/semantic/{db_id}/query/compile` — Biên dịch Metric/Dimensions thành câu lệnh SQL chuẩn dialect + chẩn đoán (Compile Preview, không query DB)
- `POST /api/v1/semantic/{db_id}/query` — Biên dịch và thực thi câu lệnh SQL an toàn trên Live DB (kèm `LIMIT 100` và `timeout = 15s`)

### 7. AI Conversational Studio & Query Clarifier Wizard

- `POST /api/v1/semantic/{db_id}/chat` — Multi-agent Chatbot tự động phân loại Intent (Chitchat tiếng Việt vs Gợi ý Metric)
- `POST /api/v1/semantic/{db_id}/query/wizard/start` — Bắt đầu phiên Wizard hỏi-đáp đa bước làm rõ câu truy vấn mơ hồ
- `POST /api/v1/semantic/{db_id}/query/wizard/step` — Nạp lựa chọn người dùng cho từng bước Wizard và trả về cấu hình truy vấn đã làm rõ

---

## 📊 Kịch bản & Mẫu Truy vấn Thực tế (Sample Queries & Scenarios)

### Kịch bản 1: Kết nối Live Target DB & Khởi chạy Flow 1 Enrichment

**1. Kết nối Target DB:**

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/db/connect" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "E-Commerce Production DB",
    "dialect": "postgresql",
    "conn_url": "postgresql://dev:devpassword@localhost:5432/ecommerce_db"
  }'
```

**2. Khởi chạy 2-Pass AI Schema Enrichment:**

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/generate" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "db_id": 1
  }'
```

**3. Phê duyệt (HITL Approve) Semantic Layer:**

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/approve" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "db_id": 1
  }'
```

---

### Kịch bản 2: Biên dịch & Thực thi Truy vấn Semantic Layer (Flow 2)

#### Ví dụ 1: Xem trước SQL biên dịch (Compile-Only Preview)

**Yêu cầu:** Tính "Tổng Doanh Thu Thuần" theo "Kênh bán hàng" trong năm 2024.

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/1/query/compile" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [1],
    "dimensions": [
      {"table": "sales_channels", "column": "channel_name"}
    ],
    "time_dimension": {
      "table": "order_header",
      "column": "created_at",
      "grain": "year"
    },
    "filters": [
      {
        "table": "order_header",
        "column": "order_status",
        "operator": "eq",
        "value": "completed"
      }
    ]
  }'
```

**Kết quả SQL Biên dịch nhận được:**

```sql
SELECT 
  sales_channels.channel_name AS "sales_channels__channel_name",
  DATE_TRUNC('year', order_header.created_at) AS "order_header__created_at_year",
  SUM(order_header.total_amount - order_header.discount_amount) AS "net_revenue"
FROM order_header
JOIN sales_channels ON order_header.sales_channel_id = sales_channels.id
WHERE order_header.order_status = 'completed'
GROUP BY sales_channels.channel_name, DATE_TRUNC('year', order_header.created_at)
ORDER BY "net_revenue" DESC
LIMIT 100;
```

#### Ví dụ 2: Thực thi truy vấn trực tiếp trên Live Database

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/1/query" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [1],
    "dimensions": [
      {"table": "sales_channels", "column": "channel_name"}
    ]
  }'
```

**Kết quả Response:**

```json
{
  "sql": "SELECT sales_channels.channel_name AS \"sales_channels__channel_name\", SUM(order_header.total_amount - order_header.discount_amount) AS \"net_revenue\" FROM order_header JOIN sales_channels ON order_header.sales_channel_id = sales_channels.id GROUP BY sales_channels.channel_name LIMIT 100",
  "parameters": {},
  "columns": [
    {"name": "sales_channels__channel_name", "type": "VARCHAR"},
    {"name": "net_revenue", "type": "NUMERIC"}
  ],
  "rows": [
    {"sales_channels__channel_name": "Online Website", "net_revenue": 1250000000.0},
    {"sales_channels__channel_name": "Shopee Mall", "net_revenue": 890000000.0},
    {"sales_channels__channel_name": "Cửa hàng Offline Hà Nội", "net_revenue": 650000000.0}
  ],
  "row_count": 3
}
```

---

### Kịch bản 3: Tương tác qua Multi-Agent Studio & AI Assistant Wizard

**1. Hỏi đáp Multi-Agent qua Chat Studio:**

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/1/chat" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Gợi ý cho tôi các chỉ số đo lường hiệu quả bán hàng và giá trị đơn hàng trung bình (AOV)"
  }'
```

**2. Bắt đầu phiên AI Query Clarifier Wizard:**

```bash
curl -X POST "http://localhost:8000/api/v1/semantic/1/query/wizard/start" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

---

### Kịch bản 4: Xuất bản Semantic Layer (Export JSON / YAML)

```bash
# Tải về định dạng YAML phục vụ tích hợp BI / dbt Semantic Layer
curl -X GET "http://localhost:8000/api/v1/semantic/1/export?format=yaml" \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -o semantic_layer_export.yaml
```

**Cấu trúc tệp YAML xuất bản mẫu:**

```yaml
semantic_layer:
  version: "2.0.0"
  database:
    name: "E-Commerce Production DB"
    dialect: "postgresql"
  entities:
    - name: "order_header"
      business_name: "Đơn hàng"
      description: "Thông tin tổng quan các giao dịch mua hàng"
      primary_key: "id"
      dimensions:
        - name: "created_at"
          business_name: "Ngày tạo đơn"
          type: "timestamp"
          is_time_dimension: true
        - name: "order_status"
          business_name: "Trạng thái đơn hàng"
          type: "varchar"
    - name: "sales_channels"
      business_name: "Kênh bán hàng"
      primary_key: "id"
  relationships:
    - from_entity: "order_header"
      to_entity: "sales_channels"
      type: "many_to_one"
      join_condition: "order_header.sales_channel_id = sales_channels.id"
  metrics:
    - name: "total_net_revenue"
      business_name: "Tổng Doanh Thu Thuần"
      base_entity: "order_header"
      aggregation: "SUM"
      formula: "order_header.total_amount - order_header.discount_amount"
      status: "active"
      version: 2
```

---

## 🧪 Kiểm thử & Đảm bảo Chất lượng (Testing Suite)

Dự án áp dụng 100% Mock LLM và Mock DB theo chuẩn quy định tại [AGENTS.md](file:///d:/project/P-069/AGENTS.md):

```bash
# 1. Kiểm tra linter & formatting chuẩn với Ruff
ruff check src/ tests/
ruff format src/ tests/

# 2. Chạy toàn bộ Test Suite (60+ unit & integration tests)
pytest

# 3. Chạy kiểm thử có hiển thị chi tiết và đo thời gian
pytest -v -s --durations=10
```

---

## 🛡️ Nguyên tắc An toàn & Bảo mật (Security Guidelines)

1. **Schema Metadata Only:** Động cơ Introspection chỉ đọc cấu trúc (`get_tables`, `get_columns`, `get_foreign_keys`), tuyệt đối không truy vấn dữ liệu nhạy cảm của khách hàng trong Flow 1.
2. **Fernet Encryption:** Mọi Connection URL của Target DB đều được mã hóa đối xứng trước khi lưu vào database và chỉ giải mã trong RAM khi cần thực thi.
3. **Double Guardrails trên Flow 2:** Ép kiểm tra AST câu lệnh qua `sqlglot` (bắt buộc duy nhất `SELECT`), tự động inject trần `LIMIT 100` (tối đa 1000 rows) và gán `statement_timeout = 15s`.
4. **Deterministic Compilation:** Biên dịch SQL theo mô hình quan hệ bảng định danh, không dùng Text-to-SQL tự do khi truy vấn dữ liệu thực tế.

---

## 📚 Tài liệu Liên quan

- 🏛️ [Architecture Document](file:///d:/project/P-069/ARCHITECTURE.md)
- 📊 [Evaluation Evidence Report (Báo cáo Đánh giá Thực nghiệm)](file:///d:/project/P-069/eval/results/report.md)
- 🗄️ [Database Design Specification](file:///d:/project/P-069/docs/DATABASE_DESIGN.md)
- 📋 [Product Requirements Document (PRD)](file:///d:/project/P-069/docs/PRD.md)
- 📑 [Feature Specifications](file:///d:/project/P-069/docs/FEATURE_SPECIFICATIONS.md)
- 🎨 [UI Flow & Wireframes](file:///d:/project/P-069/docs/UI_FLOW.md)
- 📅 [Action Plan & Tiến độ](file:///d:/project/P-069/docs/ACTION_PLAN.md)
- 📄 [Project Brief](file:///d:/project/P-069/docs/BRIEF.md)
- 📜 [Agent Rules & Guidelines](file:///d:/project/P-069/AGENTS.md)

---

## 📄 Giấy phép (License)

Dự án được phân phối theo giấy phép **MIT License**.
