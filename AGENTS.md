# AGENTS.md — AI Semantic Layer Agent

> **ĐỌC FILE NÀY TRƯỚC KHI LÀM BẤT KỲ VIỆC GÌ.**  
> Đây là nguồn sự thật duy nhất cho AI coding assistant về project này.  
> Sau khi đọc xong, đọc thêm [`ARCHITECTURE.md`](./ARCHITECTURE.md) để hiểu chi tiết kỹ thuật.

---

## 🎯 Mục tiêu dự án

Xây dựng AI Agent end-to-end với **2 pipeline**:

1. **Generate Semantic Layer** — kết nối DB → AI tự phân tích schema → tạo định nghĩa nghiệp vụ (business name, mô tả cột, business metrics) → lưu vào Metadata Store → trả về Semantic Layer JSON
2. **Query bằng ngôn ngữ tự nhiên** — đặt câu hỏi → Agent dùng Semantic Layer → generate SQL → validate → thực thi → trả kết quả data (text/table/number)

**Không phải RAG chatbot, không phải generic AI assistant.**  
Đây là công cụ NL2SQL có context nghiệp vụ thông qua Semantic Layer.

---

## 🏗️ Kiến trúc tổng quan

Chi tiết đầy đủ: [`ARCHITECTURE.md`](./ARCHITECTURE.md)

```
FastAPI (API Gateway)
  │
  ├── /api/v1/semantic/*  ──►  Flow 1: Generate Pipeline (LangGraph)
  │                               Introspect Node (SQLAlchemy)
  │                             → Enrich Node (LLM: đặt business_name)
  │                             → Metric Suggest Node (LLM: đề xuất metrics)
  │                             → Save Node (lưu Metadata Store)
  │                               Output: Semantic Layer JSON
  │
  └── /api/v1/query/*     ──►  Flow 2: Query Pipeline (LangGraph Multi-Agent)
                                  Metric Matcher (Kiểm tra xem có khớp metric đã lưu ở Flow 1 không)
                                  ├── [Match]  ──► Dùng SQL Template (Bỏ qua SQL Gen) ─┐
                                  └── [Unmatch]──► Schema Agent → SQL Gen Agent ─────┴──► Validate → Execute → Format
                                  Output: answer + SQL + raw data

Data Layer:
  ├── Target Database (PostgreSQL/MySQL/SQLite) — DB người dùng muốn query
  └── Metadata Store (PostgreSQL dev & prod) — lưu Semantic Layer
```

---

## 📁 Cấu trúc thư mục

```
src/
├── agents/
│   ├── generate/                    # Flow 1 — Generate Pipeline
│   │   ├── graph.py                 #   LangGraph StateGraph (build_generate_graph)
│   │   ├── state.py                 #   GenerateState TypedDict
│   │   └── nodes/
│   │       ├── introspect_node.py   #   SQLAlchemy schema introspection
│   │       ├── enrich_node.py       #   LLM: business_name + description
│   │       ├── metric_suggest_node.py #  LLM: đề xuất business metrics
│   │       └── save_node.py         #   Lưu vào Metadata Store
│   └── query/                       # Flow 2 — Query Pipeline
│       ├── graph.py                 #   LangGraph StateGraph (build_query_graph)
│       ├── state.py                 #   QueryState TypedDict
│       └── nodes/
│           ├── schema_node.py       #   LLM chọn bảng liên quan từ metadata
│           ├── sql_gen_node.py      #   LLM generate SQL
│           ├── validate_node.py     #   sqlparse: whitelist SELECT only
│           ├── execute_node.py      #   SQLAlchemy read-only execute
│           └── format_node.py       #   Format output → text/table/number
├── api/
│   └── routes/
│       ├── semantic.py              #   /api/v1/semantic/*
│       └── query.py                 #   /api/v1/query/*
├── db/
│   ├── models.py                    #   SQLAlchemy ORM cho Metadata Store
│   └── session.py                   #   DB session factory
├── models/
│   └── schemas.py                   #   Pydantic request/response schemas
├── services/
│   ├── llm.py                       #   get_llm() factory — LUÔN dùng cái này
│   ├── schema_service.py            #   SQLAlchemy introspection helpers
│   ├── metadata_service.py          #   CRUD cho Metadata Store
│   └── safety_service.py            #   sqlparse SQL validation
├── config.py                        #   pydantic-settings (đọc .env)
└── main.py                          #   FastAPI app entry point
```

---

## 🔌 API Endpoints

### Flow 1 — Semantic Layer Management (`/api/v1/semantic/`)

| Method | Path | Input | Output |
|--------|------|-------|--------|
| POST | `/generate` | `{ connection_url, db_name }` | Semantic Layer JSON |
| GET | `/{db_id}` | — | Semantic Layer đã lưu |
| PUT | `/{db_id}/table/{table}` | `{ business_name, description }` | Updated |
| PUT | `/{db_id}/column/{table}/{col}` | `{ business_name, description }` | Updated |
| POST | `/{db_id}/metric` | `{ name, description, sql_template }` | New metric |

### Flow 2 — Query (`/api/v1/query/`)

| Method | Path | Input | Output |
|--------|------|-------|--------|
| POST | `/` | `{ db_id, question }` | `{ answer, format }` |
| POST | `/sql` | `{ db_id, question }` | `{ answer, sql, data, format }` |

---

## ⚙️ Environment Variables (.env)

```env
# App
APP_ENV=development          # development | production | test
APP_PORT=8000
LOG_LEVEL=DEBUG

# LLM — BẮT BUỘC
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
LLM_TEMPERATURE=0.0          # LUÔN 0.0 cho NL2SQL (cần deterministic)

# Metadata Store (PostgreSQL dev & prod)
DATABASE_URL=postgresql+psycopg2://dev:devpassword@localhost:5432/semantic_layer_dev

# CORS
CORS_ORIGINS=http://localhost:3000
```

---

## 📦 Tech Stack (requirements.txt)

```
fastapi, uvicorn[standard]       — API layer
pydantic v2, pydantic-settings   — validation + config
langgraph, langchain             — agent orchestration
langchain-openai                 — GPT-4o-mini
langchain-community              — SQLDatabaseToolkit
sqlalchemy, alembic              — ORM + migrations
psycopg2-binary                  — PostgreSQL driver (dev & prod)
sqlparse                         — SQL safety validation
ruff, pytest, pytest-asyncio, httpx — dev tools
```

**Không dùng:** ChromaDB, FAISS, hay bất kỳ vector store nào — không cần cho bài toán này.

---

## 🚦 Quy tắc BẮT BUỘC

### 🔴 SQL Safety (CRITICAL)
- Agent **CHỈ ĐƯỢC PHÉP** chạy `SELECT` trên Target DB
- Dùng `sqlparse` trong `safety_service.py` kiểm tra trước khi execute
- Hard limit: **1000 rows** per query
- Timeout: **30 giây** per query
- Connection URL **không bao giờ** lưu plaintext — phải encrypt

### 🔴 LLM Usage
- **Luôn dùng `get_llm()`** từ `src/services/llm.py` — không khởi tạo `ChatOpenAI` trực tiếp ở nơi khác
- Temperature = `0.0` cho **tất cả node liên quan SQL** (schema_node, sql_gen_node, validate_node)
- Prompt NL2SQL phải có few-shot examples để tăng accuracy

### 🔴 Code Style
- **Async everywhere** — tất cả node, service, route đều phải `async def`
- **Type hint đầy đủ** — đặc biệt State TypedDict và function signatures
- **Max 30 lines** per function — dài hơn thì tách ra
- **Docstring tiếng Anh** cho public functions
- **Ruff** để lint và format: `ruff check src/` và `ruff format src/`
- **Import order:** stdlib → third-party → local (ruff tự sort)

### 🔴 Testing
- Mỗi node phải có unit test trong `tests/test_agents/`
- **Mock LLM** trong tests — không gọi OpenAI API thật
- **Mock DB** trong tests — dùng SQLite in-memory
- Chạy tests: `pytest tests/ -v`

### 🔴 AI Usage Logging (ĐỪNG ĐỘNG VÀO)
- **KHÔNG** chạy `scripts/log_antigravity.py` hay bất kỳ log script nào sau mỗi task
- Logging đã tự động qua pre-push hook khi `git push`
- Nếu user dùng ChatGPT/web tool → hướng họ tới `.agents/workflows/log.md`
- **KHÔNG** sửa hay xóa file trong `.ai-log/`

---

## 🗄️ Metadata Store Schema

```sql
semantic_databases  (id, name, db_type, conn_url_enc, created_at)
semantic_tables     (id, db_id, table_name, business_name, description)
semantic_columns    (id, table_id, column_name, business_name, description, data_type, example_values)
semantic_metrics    (id, db_id, name, description, sql_template)
```

---

## ❌ KHÔNG LÀM

| Cấm | Lý do |
|-----|-------|
| `eval()` / `exec()` với SQL string | Security risk |
| Raw string format cho SQL | SQL injection |
| Hardcode API key / connection URL | Secret leak |
| Thêm dependency không có trong `requirements.txt` | Phải update file đó |
| Chạy `UPDATE`, `DELETE`, `INSERT`, `DROP` trên Target DB | Read-only |
| Commit `.env` | Secret leak |
| Import `ChatOpenAI` trực tiếp ngoài `llm.py` | Phải dùng `get_llm()` |
| Bare `except:` | Che lỗi, khó debug |
| Function > 30 lines | Tách ra |
| Code trong 1 file > 500 lines | Tách module |

---

## 🚀 Chạy local

```bash
# Dev với hot-reload (khuyên dùng)
docker compose -f docker-compose.dev.yml up --build

# Không Docker
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# Swagger UI: http://localhost:8000/docs
```

---

## 🧪 Chạy tests

```bash
pytest tests/ -v                    # tất cả
pytest tests/test_agents/ -v       # chỉ agent tests
pytest tests/test_api/ -v          # chỉ API tests
ruff check src/ tests/             # lint
ruff format src/ tests/            # format
```

---

## 📖 Tài liệu tham khảo (trong repo)

| File | Nội dung |
|------|---------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Kiến trúc chi tiết, diagrams, state schemas |
| [`docs/guide/langgraph/nodes-and-edges.md`](./docs/guide/langgraph/nodes-and-edges.md) | Cách viết nodes + edges đúng |
| [`docs/guide/langgraph/state.md`](./docs/guide/langgraph/state.md) | State TypedDict patterns |
| [`docs/guide/code-style/python.md`](./docs/guide/code-style/python.md) | Python code conventions |
| [`docs/guide/anti-patterns/cohort-1-mistakes.md`](./docs/guide/anti-patterns/cohort-1-mistakes.md) | Lỗi thường gặp từ Cohort 1 |
| [`docs/guide/testing/writing-tests.md`](./docs/guide/testing/writing-tests.md) | Cách viết tests |
| [`docs/guide/troubleshooting.md`](./docs/guide/troubleshooting.md) | Debug guide |
