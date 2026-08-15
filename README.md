# 🤖 AI Semantic Layer Agent — P-069

> **Dự án thuộc VinUni AI20K Build Phase (Cohort 3)**  
> **Hệ thống AI Agent hỗ trợ xây dựng và quản trị lớp ngữ nghĩa dữ liệu (Semantic Layer) & định nghĩa chỉ số kinh doanh thống nhất.**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6F61?style=flat)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Tổng quan bài toán (Problem Statement)

Trong các doanh nghiệp, dữ liệu lưu trữ tại cơ sở dữ liệu (PostgreSQL, MySQL, SQLite) thường gặp **2 thách thức lớn**:

1. **Khoảng cách Ngữ cảnh Nghiệp vụ (Business Context Gap):** Tên bảng và cột mang tính kỹ thuật khô khan (vd: `usr_tbl_01`, `amt_vat_inc`, `ord_sts_cd`), khiến người dùng nghiệp vụ hoặc BA/DA mất thời gian giải thích và diễn giải số liệu.
2. **Hỗn loạn Định nghĩa Chỉ số (Metric Definition Chaos):** Thiếu một "nguồn sự thật duy nhất" (Single Source of Truth) cho các công thức tính chỉ số (doanh thu, churn rate, conversion rate...). Mỗi phòng ban tự tính theo cách riêng dẫn đến số liệu báo cáo không thống nhất.

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

## 🏗 Kiến trúc hệ thống (System Architecture)

Hệ thống xây dựng theo mô hình 3-Tier với **LangGraph StateGraph** điều phối pipeline có nút **Interrupt (HITL)**:

```mermaid
flowchart TD
    START(["Client / UI Request\n(Connection URL)"]) --> IN

    subgraph Pipeline["⚙️ LangGraph Flow 1 Pipeline"]
        IN["🔍 Introspect Node\nSQLAlchemy Inspector\n(Schema Metadata Only)"]
        IN --> EN
        
        EN["📝 Enrich Node\nGPT-4o-mini đặt business_name\n& mô tả tiếng Việt"]
        EN --> MS
        
        MS["💡 Metric Suggest Node\nGPT-4o-mini đề xuất\nBusiness Metrics + SQL Template"]
        MS --> HITL
        
        HITL{"👤 HITL Review Node\n(LangGraph Interrupt)\nBA/DA duyệt & chỉnh sửa"}
        
        HITL -->|"✅ Approve"| SV["💾 Save Node\nPersist vào Metadata Store"]
        HITL -->|"🔄 Request Re-enrich"| EN
    end

    SV --> EX["📤 Export Service\nJSON / YAML File"]
    EX --> END(["✅ Complete Semantic Layer"])

    IN -.- TARGET[("🗄️ Target DB\n(Postgres/MySQL/SQLite)")]
    SV -.- METADB[("🗄️ Metadata Store\n(PostgreSQL)")]
```

---

## 🛠 Tech Stack

| Thành phần | Công nghệ | Phiên bản | Vai trò |
|---|---|---|---|
| **Core & Framework** | Python / FastAPI | 3.11 / ≥ 0.115 | Language & Async REST API |
| **Agent Orchestration** | LangGraph | ≥ 0.2 | StateGraph & HITL Interrupt |
| **LLM Provider** | OpenAI GPT-4o-mini | API (Temp = 0.0) | Sinh tên nghiệp vụ & gợi ý metric |
| **Database Abstraction** | SQLAlchemy | ≥ 2.0 | Metadata Inspector & ORM |
| **Metadata Store** | PostgreSQL | 16-alpine | Lưu thông tin Semantic Layer |
| **Security** | Cryptography (Fernet) | Standard | Mã hóa Connection URL |
| **Export Formats** | PyYAML / JSON | Standard | Đóng gói Semantic Layer cho BI |
| **DevOps & Quality** | Docker / Docker Compose / Ruff | Standard | Containerization & Linting |

---

## 📁 Cấu trúc thư mục dự án

```
P-069/
├── src/
│   ├── agents/               # 🧠 LangGraph Agent Pipeline
│   │   ├── nodes/            #    Các node: introspect, enrich, metric_suggest, save
│   │   ├── graph.py          #    Định nghĩa StateGraph & Routing logic
│   │   └── state.py          #    AgentState TypedDict schema
│   ├── api/                  # 🌐 FastAPI Routes & Endpoints
│   │   ├── auth.py           #    Authentication routes (register, login, Google OAuth)
│   │   └── routes.py         #    Flow 1 REST endpoints & CRUD Metrics
│   ├── models/               # 📋 Pydantic Schemas & DB Models
│   │   ├── db.py             #    SQLAlchemy ORM models
│   │   └── schemas.py        #    Request/Response Validation Models
│   ├── services/             # 🔧 Core Services (LLM, Security, Export)
│   │   ├── database.py       #    Fernet encryption + AsyncEngine/Session
│   │   ├── export_service.py #    JSON/YAML export
│   │   └── llm.py            #    get_llm() factory (OpenAI GPT-4o-mini)
│   ├── config.py             # ⚙️ App Settings (Pydantic-settings)
│   └── main.py               # 🚀 FastAPI App Entry Point
├── tests/                    # 🧪 Test Suite (pytest)
│   ├── test_agents/          #    Unit tests cho từng node & graph
│   ├── test_api/             #    Integration tests cho API endpoints
│   └── test_models/          #    ORM model & encryption tests
├── docs/                     # 📚 Tài liệu chi tiết dự án
│   ├── BRIEF.md              #    Project Brief
│   ├── PRD.md                #    Product Requirements Document
│   ├── UI_FLOW.md            #    Giao diện & HITL Interaction Flow
│   └── ACTION_PLAN.md        #    Kế hoạch triển khai dự án
├── alembic/                  # 🗄️ Alembic Database Migration scripts
│   ├── versions/             #    Chứa các file migration (.py)
│   └── env.py                #    Cấu hình AsyncEngine migration
├── alembic.ini               # ⚙️ alembic configuration
├── scripts/                  # 🔌 AI Usage Logging Hooks
├── ARCHITECTURE.md           # 🏛 Architecture Specification
├── AGENTS.md                 # 📜 AI Assistant Rules & Guidelines
├── docker-compose.dev.yml    # 🐳 Docker Compose cho Development (Hot-reload + Postgres)
├── docker-compose.yml        # 🐙 Docker Compose cho Production
├── Dockerfile                # 🐳 Dockerfile Multi-stage Build
├── requirements.txt          # 📦 Python Dependencies
└── README.md                 # 📖 Tài liệu dự án (File này)
```

---

## ⚡ Quick Start & Hướng dẫn cài đặt

### 1. Yêu cầu tiên quyết
- **Python:** `3.11+`
- **Docker & Docker Compose** (nếu chạy container)
- **Git**

### 2. Clone repository & Môi trường Virtualenv

```bash
# Clone dự án
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-069.git
cd P-069

# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Hoặc trên Linux/macOS:
# source .venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (`.env`)

Sao chép file `.env.example` thành `.env` và bổ sung các API Key:

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

# Metadata Store DB Connection (PostgreSQL with asyncpg driver)
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
* **Metadata Store (PostgreSQL / SQLite):** Lưu thông tin người dùng, phiên đăng nhập, kết nối Target DB (đã mã hóa), bảng/cột được enrich và Business Metrics.
* **Target DB (Chỉ đọc Schema):** Cơ sở dữ liệu nghiệp vụ của doanh nghiệp. Agent chỉ kết nối qua `SQLAlchemy Inspector` để đọc cấu trúc (Tables/Columns/FKs), **không thực thi truy vấn đọc dữ liệu (SELECT)**.

### 1. Khởi tạo Metadata Store với Docker & PgWeb

Khởi chạy PostgreSQL 16 và giao diện quản trị Web GUI (PgWeb):

```bash
# Khởi chạy Postgres DB & PgWeb UI trong background
docker compose -f docker-compose.dev.yml up postgres pgweb -d
```

* **PostgreSQL:** `localhost:5432` | User: `dev` | Password: `devpassword` | DB: `semantic_layer_dev`
* **PgWeb UI (Giao diện Web xem DB):** Mở trình duyệt tại [http://localhost:8081](http://localhost:8081)

### 2. Quản trị Migration Cấu trúc Database (Alembic)

Dự án tích hợp sẵn **Alembic** để tự động hóa migration cho Metadata Store (PostgreSQL / SQLite).

```bash
# 1. Cập nhật DB Schema lên phiên bản mới nhất (chạy khi setup ban đầu)
alembic upgrade head

# 2. (Dành cho Dev) Tự động sinh file migration mới khi chỉnh sửa SQLAlchemy ORM Model (src/models/db.py)
alembic revision --autogenerate -m "describe_your_changes"

# 3. Xem lịch sử các bản migration đã áp dụng
alembic history --verbose

# 4. Rollback 1 bản migration gần nhất
alembic downgrade -1
```

### 3. Tạo Secret Key mã hóa Connection URL (Fernet Encryption)

Chuỗi kết nối (`conn_url`) đến Target DB **không bao giờ lưu ở dạng plaintext**. Bạn cần sinh `ENCRYPTION_KEY` và điền vào `.env`:

```bash
# Sinh Fernet Key bằng Python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Khởi tạo Target DB Thử nghiệm (Golden Retail Benchmark DB)

Dự án cung cấp sẵn bộ dữ liệu mẫu **Golden Retail Database** (36 bảng DDL, 5.000 đơn hàng, 1.000 khách hàng, 8.000 phiên web, 8.5 MB seed dataset) để phục vụ thử nghiệm tính năng Introspection và biên dịch Query.

1. Khởi chạy container PostgreSQL (nếu chưa chạy):
   ```bash
   docker compose -f docker-compose.dev.yml up postgres -d
   ```

2. Chạy script khởi tạo Target DB:
   ```bash
   python scripts/setup_target_db.py
   ```
   *Lưu ý:* Script hoàn toàn tự động! Nếu chưa có sẵn file seed SQL, script sẽ tự động gọi `scripts/seed_data_generator.py` và `scripts/convert_to_postgres.py` để sinh dữ liệu và nạp vào database `golden_retail_db`.

3. **Connection URL của Target DB thử nghiệm**:
   - **Khi chạy Backend trong Docker Container (`docker compose`):**
     ```text
     postgresql://dev:devpassword@postgres:5432/golden_retail_db
     ```
   - **Khi chạy Backend trên Local máy (`uvicorn`):**
     ```text
     postgresql://dev:devpassword@localhost:5432/golden_retail_db
     ```

---

## 🚀 Chạy ứng dụng

### Cách 1: Chạy trực tiếp qua Uvicorn (Local Dev)

1. Khởi động PostgreSQL Metadata Store qua Docker Compose (hoặc dùng Postgres local):
```bash
docker compose -f docker-compose.dev.yml up postgres pgweb -d
```

2. Khởi chạy FastAPI App Server:
```bash
uvicorn src.main:app --reload --port 8000
```

3. Mở tài liệu API Swagger tại: [http://localhost:8000/docs](http://localhost:8000/docs)

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
|---|---|---|
| `POST` | `/api/v1/semantic/generate` | Khởi chạy Flow 1 (Introspect DB → Enrich → Suggest Metrics) |
| `POST` | `/api/v1/semantic/approve` | Xác nhận (Approve) từ HITL review & persist vào Metadata Store |
| `PUT` | `/api/v1/semantic/{db_id}/table/{table_name}` | Cập nhật tên/mô tả nghiệp vụ của bảng (HITL Inline Edit) |
| `PUT` | `/api/v1/semantic/{db_id}/column/{table_name}/{column_name}` | Cập nhật tên/mô tả nghiệp vụ của cột (HITL Inline Edit) |
| `POST` | `/api/v1/semantic/{db_id}/metric` | Tạo mới một Business Metric (AI hoặc Thủ công) |
| `PUT` | `/api/v1/semantic/{db_id}/metric/{metric_id}` | Cập nhật Business Metric đã tồn tại |
| `DELETE`| `/api/v1/semantic/{db_id}/metric/{metric_id}` | Xóa Business Metric |
| `GET` | `/api/v1/semantic/{db_id}/export?format=json\|yaml` | Xuất Semantic Layer đã phê duyệt ra JSON hoặc YAML |
| `GET` | `/api/v1/status` | Kiểm tra trạng thái sẵn sàng của Agent |

---

## 🧪 Testing & Code Quality

Dự án tuân thủ nghiêm ngặt quy trình kiểm thử (Async unit test & Async API test with mock DB/LLM):

```bash
# Kiểm tra linting & format bằng Ruff
ruff check src/
ruff format src/

# Chạy toàn bộ test suite
pytest

# Chạy test kèm thông tin chi tiết
pytest -v -s
```

---

## 🛡️ Quy tắc An toàn & Bảo mật (Security Guidelines)

1. **Schema Metadata Only:** Động cơ Introspection chỉ gọi `SQLAlchemy Inspector` để lấy cấu trúc dữ liệu (`get_tables`, `get_columns`, `get_foreign_keys`). **Không bao giờ thực thi câu lệnh SQL SELECT data**.
2. **URL Encryption:** Connection URL của Target DB bắt buộc mã hóa qua `cryptography` Fernet trước khi lưu vào `semantic_databases.conn_url_enc`.
3. **Human Approval:** Kết quả sinh ra từ AI phải trải qua nút HITL Interrupt trước khi ghi nhận chính thức vào Metadata Store.

---

## 📖 Tài liệu liên quan

- 🏛️ [Architecture Specification](file:///d:/project/P-069/ARCHITECTURE.md)
- 📜 [Agent Rules & Guidelines](file:///d:/project/P-069/AGENTS.md)
- 📄 [Project Brief](file:///d:/project/P-069/docs/BRIEF.md)
- 📋 [Product Requirements Document (PRD)](file:///d:/project/P-069/docs/PRD.md)
- 🎨 [UI & HITL Flow](file:///d:/project/P-069/docs/UI_FLOW.md)
- 📅 [Action Plan](file:///d:/project/P-069/docs/ACTION_PLAN.md)

---

## 📄 License

Dự án được phân phối theo giấy phép **MIT License**.

