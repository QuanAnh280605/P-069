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
- **Node.js:** `18+` & `npm`
- **Docker & Docker Compose**
- **Git**

### 2. Cài đặt Backend

```bash
# Clone repository
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-069.git
cd P-069

# Tạo & kích hoạt virtualenv
python -m venv .venv
# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
# source .venv/bin/activate

# Cài đặt dependencies backend
pip install -r requirements.txt
```

### 3. Cấu hình Biến môi trường (`.env`)

Sao chép `.env.example` thành `.env` và cập nhật các thông số:

```bash
cp .env.example .env
```

Nội dung `.env` chính:

```env
APP_ENV=development
LOG_LEVEL=INFO

# LLM: preset có sẵn (openai | gemini | groq | mimo | anthropic)
# Alias: google -> gemini, claude -> anthropic
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-xxxx...
MODEL_NAME=gpt-4o-mini

# LLM: hoặc trỏ tới BẤT KỲ endpoint OpenAI-compatible (vLLM, Ollama, proxy nội bộ,
# DeepSeek, OpenRouter...) — không cần sửa code, 3 biến này thắng mọi preset ở trên
# LLM_PROVIDER=custom
# LLM_API_BASE=http://localhost:8000/v1
# LLM_API_KEY=sk-local
# LLM_MODEL=qwen2.5-32b-instruct

# LLM: model riêng cho từng bước (để trống = dùng model chung ở trên)
# LLM_MODEL_ENRICH=llama-3.1-8b-instant     # sinh tên nghiệp vụ cho schema
# LLM_MODEL_METRIC=llama-3.3-70b-versatile  # đề xuất business metric

# LLM: chỉ set khi endpoint KHÔNG phải OpenAI-compatible (hỗ trợ: openai | anthropic)
# LLM_PROTOCOL=anthropic

# Secret Key mã hóa Fernet cho Target DB Connection URL
ENCRYPTION_KEY=your_fernet_base64_key_here

# Metadata Store Database Connection (PostgreSQL asyncpg)
DATABASE_URL=postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev
```

Thứ tự ưu tiên khi resolve LLM (lấy giá trị khác rỗng đầu tiên): `LLM_API_BASE` →
`<PROVIDER>_API_BASE` → default trong code; `LLM_API_KEY` → `<PROVIDER>_API_KEY` →
`OPENAI_API_KEY`; `LLM_MODEL_<ROLE>` → `LLM_MODEL` → `MODEL_NAME` → default theo
provider. Provider lạ mà thiếu `LLM_API_BASE`, hoặc thiếu API key với endpoint remote,
sẽ báo lỗi rõ ràng ngay lúc khởi tạo client (không âm thầm gọi `api.openai.com`);
endpoint `localhost` được miễn API key. Xem [`.env.example`](./.env.example) cho danh
sách biến đầy đủ.

Đổi provider/model chỉ cần sửa `.env`: khi `APP_ENV=development`, `get_llm()` tự phát
hiện `.env` thay đổi (theo mtime) và tạo lại client — không cần restart server. Ở môi
trường khác, gọi `reload_llm_config()` từ `src/services/llm.py` hoặc restart. Client
được cache theo config nên nhiều node dùng cùng model sẽ dùng chung một instance.

*(Mẹo: Bạn có thể sinh Fernet Key nhanh bằng Python: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)*

### 4. Thiết lập AI Usage Logging Hooks (Dành cho Học viên VinUni AI20K)

```bash
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1

# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh
```

---

## 🗄️ Hướng dẫn Khởi tạo & Quản trị Cơ sở Dữ liệu (Database Setup & Management)

Hệ thống phân biệt rõ ràng **2 nhóm Cơ sở Dữ liệu**:
- **Metadata Store (PostgreSQL / SQLite):** Lưu thông tin người dùng, phiên đăng nhập, kết nối Target DB (đã mã hóa), bảng/cột được enrich và Business Metrics.
- **Target DB (Chỉ đọc Schema):** Cơ sở dữ liệu nghiệp vụ của doanh nghiệp. Agent chỉ kết nối qua `SQLAlchemy Inspector` để đọc cấu trúc (Tables/Columns/FKs), **không thực thi truy vấn đọc dữ liệu (SELECT)**.

### 1. Khởi tạo Metadata Store với Docker & PgWeb

Khởi chạy PostgreSQL 16 và giao diện quản trị Web GUI (PgWeb):

```bash
# Khởi chạy Postgres DB & PgWeb UI trong background
docker compose -f docker-compose.dev.yml up postgres pgweb -d

# 2. Cập nhật Database Schema lên bản mới nhất
alembic upgrade head

# 3. Nạp bộ dữ liệu thử nghiệm Golden Retail Database (36 bảng, 5.000 orders)
python scripts/setup_target_db.py
```

- **PgWeb UI:** Mở trình duyệt tại [http://localhost:8081](http://localhost:8081) để xem trực tiếp cấu trúc DB.

---

## 🚀 Khởi chạy Ứng dụng

### Cách 1: Chạy trực tiếp qua Uvicorn (Local Dev)

1. Khởi động PostgreSQL Metadata Store qua Docker Compose (hoặc dùng Postgres local):

```bash
# Chạy uvicorn với hot-reload
uvicorn src.main:app --reload --port 8000
```

1. Mở tài liệu API Swagger tại: [http://localhost:8000/docs](http://localhost:8000/docs)

### Cách 2: Chạy full-stack với Docker Compose

```bash
# Development Mode (Hot-reload code + Debug port 5678)
docker compose -f docker-compose.dev.yml up --build -d

# Xem log server
docker compose -f docker-compose.dev.yml logs -f backend

# Dừng môi trường dev
docker compose -f docker-compose.dev.yml down

# Xóa image cũ
docker image prune -f
```

---

## 🔗 Danh sách API Endpoints chính

| Method | Endpoint | Mô tả |
| --- | --- | --- |
| `POST` | `/api/v1/semantic/generate` | Khởi chạy Flow 1 (Introspect DB → Enrich → Suggest Metrics) |
| `POST` | `/api/v1/semantic/approve` | Xác nhận (Approve) từ HITL review & persist vào Metadata Store |
| `PUT` | `/api/v1/semantic/{db_id}/table/{table_name}` | Cập nhật tên/mô tả nghiệp vụ của bảng (HITL Inline Edit) |
| `PUT` | `/api/v1/semantic/{db_id}/column/{table_name}/{column_name}` | Cập nhật tên/mô tả nghiệp vụ của cột (HITL Inline Edit) |
| `POST` | `/api/v1/semantic/{db_id}/metric` | Tạo mới một Business Metric (AI hoặc Thủ công) |
| `PUT` | `/api/v1/semantic/{db_id}/metric/{metric_id}` | Cập nhật Business Metric đã tồn tại |
| `DELETE` | `/api/v1/semantic/{db_id}/metric/{metric_id}` | Xóa Business Metric |
| `GET` | `/api/v1/semantic/{db_id}/export?format=json\|yaml` | Xuất Semantic Layer đã phê duyệt ra JSON hoặc YAML |
| `GET` | `/api/v1/status` | Kiểm tra trạng thái sẵn sàng của Agent |

---

## 🧪 Kiểm thử & Chất lượng Mã nguồn (Testing)

Dự án áp dụng quy chuẩn kiểm thử nghiêm ngặt với 100% Mock LLM và Mock DB:

```bash
# Kiểm tra linter & formatting với Ruff
ruff check src/
ruff format src/

# Chạy toàn bộ Test Suite (Unit & Integration tests)
pytest

# Chạy test kèm thông tin chi tiết
pytest -v -s
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
