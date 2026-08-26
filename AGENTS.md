# AGENTS.md — AI Coding Assistant Rules

---

## 1. 📚 Tài liệu tham khảo

Đọc khi cần — không bắt buộc phải đọc hết trước mỗi task:

| File | Khi nào cần đọc |
|------|-----------------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Cần hiểu kiến trúc, folder structure, API endpoints, DB schema, tech stack |
| [`docs/PRD.md`](./docs/PRD.md) | Cần hiểu tính năng, User Stories, Acceptance Criteria |
| [`docs/BRIEF.md`](./docs/BRIEF.md) | Cần hiểu tổng quan dự án, mục tiêu, scope |
| [`docs/ACTION_PLAN.md`](./docs/ACTION_PLAN.md) | Cần biết tiến độ, task list, timeline |
| [`docs/guide/langgraph/nodes-and-edges.md`](./docs/guide/langgraph/nodes-and-edges.md) | Đang viết LangGraph nodes hoặc edges |
| [`docs/guide/langgraph/state.md`](./docs/guide/langgraph/state.md) | Đang định nghĩa hoặc sửa State TypedDict |
| [`docs/guide/code-style/python.md`](./docs/guide/code-style/python.md) | Không chắc về convention Python trong project |
| [`docs/guide/anti-patterns/cohort-1-mistakes.md`](./docs/guide/anti-patterns/cohort-1-mistakes.md) | Đang debug hoặc review code |
| [`docs/guide/troubleshooting.md`](./docs/guide/troubleshooting.md) | Đang debug lỗi |
| [`docs/guide/testing/writing-tests.md`](./docs/guide/testing/writing-tests.md) | Đang viết tests |

---

## 2. 🎯 Bài toán trong 3 dòng

**AI Agent xây dựng Semantic Layer & định nghĩa chỉ số thống nhất, hỗ trợ Truy vấn Dữ liệu.**  
Hỗ trợ 2 luồng chính:  
- **Flow 1 (Generate & Manage):** Introspect DB schema (Live DB / SQL Dump) → LLM đề xuất tên nghiệp vụ & Business Metrics → HITL review → Lưu → Export.  
- **Flow 2 (Semantic Layer Querying — CHỈ DÙNG CHO CONNECTION STRING / LIVE DB):** Biên dịch chỉ số (Metrics) & kích thước (Dimensions) được chọn thành câu lệnh SQL bằng `SemanticQueryCompiler` và thực thi Read-Only trên Live DB. *Không dùng Text-to-SQL tự do. SQL Dump không hỗ trợ Flow 2.*

---

## 3. 🚦 Quy tắc BẮT BUỘC

### 🔴 Schema Introspection & Query Execution (CRITICAL)
- **Flow 1 (Introspection):** CHỈ ĐƯỢC PHÉP dùng `SQLAlchemy Inspector` để đọc **schema metadata**.
- **Flow 2 (Query Execution — Chỉ cho Live DB):**
  - **CHỈ cho phép thực thi câu lệnh `SELECT` (Read-Only)** được biên dịch qua `SemanticQueryCompiler` dựa trên Metrics/Dimensions đã duyệt ở Flow 1.
  - **BẮT BUỘC Guardrails:** Auto-append `LIMIT 100` (max 1000), `statement_timeout` = 15s.
  - **TUYỆT ĐỐI CẤM** các câu lệnh thay đổi dữ liệu: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`.
  - **SQL Dump:** Vẫn giữ nguyên tắc CHỈ read schema metadata, không hỗ trợ query.
- Connection URL **không bao giờ** lưu plaintext — phải mã hóa Fernet (`cryptography`).

### 🔴 Database & Migrations
- **Bắt buộc tạo migration mới khi thay đổi DB schema**: Mỗi khi sửa đổi Database schema (models/tables/fields), **PHẢI** tạo 1 file Alembic migration mới (`alembic revision --autogenerate -m "..."`)
- **KHÔNG** sửa trực tiếp DB schema cũ, không chỉnh sửa migration script cũ đã apply, không drop/recreate database để tránh làm mất/hỏng dữ liệu hoặc ảnh hưởng đến các user khác

### 🔴 LLM Usage
- **Luôn dùng `get_llm()`** từ `src/services/llm.py` — không khởi tạo `ChatOpenAI` trực tiếp
- Temperature = `0.0` cho tất cả node
- Prompt sinh `business_name` phải yêu cầu output tiếng Việt

### 🔴 Code Style
- **Async everywhere** — node, service, route đều phải `async def`
- **Type hint đầy đủ** cho State TypedDict và function signatures
- **Max 30 lines** mỗi function — dài hơn thì tách
- **Docstring tiếng Anh** cho public functions
- Dùng **Ruff** để lint & format: `ruff check src/` và `ruff format src/`
- **Import order:** stdlib → third-party → local

### 🔴 Dependency
- Thêm package mới → **phải cập nhật `requirements.txt`** trước khi dùng
- **Được phép dùng:** `sqlglot` cho SQL AST validation & guardrail injection trong Flow 2.
- **Không dùng:** ChromaDB, FAISS, hay vector store nào

### 🔴 Testing
- Mỗi node/service phải có unit test trong `tests/`
- **Mock LLM** trong tests — không gọi OpenAI API thật
- **Mock DB** — dùng SQLite in-memory

### 🔴 AI Usage Logging (ĐỪNG ĐỘNG VÀO)
- **KHÔNG** chạy `scripts/log_antigravity.py` hay log script nào sau task
- Logging tự động qua pre-push hook khi `git push`
- Nếu user dùng ChatGPT/web tool → hướng tới `.agents/workflows/log.md`
- **KHÔNG** sửa hay xóa file trong `.ai-log/`

---

## 4. ❌ KHÔNG LÀM

| Cấm | Lý do |
|-----|-------|
| Thực thi câu lệnh `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` trên Target DB | Bảo vệ an toàn dữ liệu khách hàng |
| Chạy Text-to-SQL tự do | Thiếu kiểm soát, nguy cơ ảo giác và rủi ro security |
| Query dữ liệu trên SQL Dump files | SQL Dump chỉ chứa DDL cấu trúc, không có runtime DB |
| Sửa trực tiếp DB schema / Drop DB không qua Alembic migration mới | Tránh mất dữ liệu, làm hỏng DB và ảnh hưởng tới user khác |
| `eval()` / `exec()` với SQL string | Security risk |
| Hardcode API key / connection URL | Secret leak |
| Lưu connection URL plaintext | Phải dùng Fernet encrypt |
| Import `ChatOpenAI` trực tiếp ngoài `llm.py` | Phải dùng `get_llm()` |
| Bare `except:` | Che lỗi, khó debug |
| Function > 30 lines | Tách ra |
| Code trong 1 file > 500 lines | Tách module |
| Commit `.env` | Secret leak |
| Commit SQL dump / data dump chứa dữ liệu thật | PII & secret leak — đã `.gitignore` (`scratch/`, `*.dump.sql`) |
| Commit feature/code trực tiếp lên nhánh `production` | Production chỉ nhận code qua merge từ `main` (release PR); commit tay gây diverge & conflict hàng loạt |
