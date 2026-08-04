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

**AI Agent xây dựng Semantic Layer & định nghĩa chỉ số thống nhất.**  
Chỉ có **1 pipeline (Flow 1)**: Introspect DB schema → LLM đề xuất tên nghiệp vụ & Business Metrics → HITL review → Lưu → Export.  
**Không phải NL2SQL chatbot. Không implement Flow 2 trong v1.0.**

---

## 3. 🚦 Quy tắc BẮT BUỘC

### 🔴 Schema Introspection (CRITICAL)
- **CHỈ ĐƯỢC PHÉP** dùng `SQLAlchemy Inspector` để đọc **schema metadata**
- **KHÔNG** thực thi bất kỳ câu truy vấn SELECT data nào trên Target DB
- Connection URL **không bao giờ** lưu plaintext — phải mã hóa Fernet (`cryptography`)

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
- **Không dùng:** `sqlparse`, `langchain-community` — thuộc Flow 2 (Future)
- **Không dùng:** ChromaDB, FAISS, hay vector store nào

### 🔴 Testing
- Mỗi node phải có unit test trong `tests/test_agents/`
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
| Thực thi `SELECT` data trên Target DB | Chỉ đọc schema metadata |
| `eval()` / `exec()` với SQL string | Security risk |
| Hardcode API key / connection URL | Secret leak |
| Lưu connection URL plaintext | Phải dùng Fernet encrypt |
| Import `ChatOpenAI` trực tiếp ngoài `llm.py` | Phải dùng `get_llm()` |
| Bare `except:` | Che lỗi, khó debug |
| Function > 30 lines | Tách ra |
| Code trong 1 file > 500 lines | Tách module |
| Commit `.env` | Secret leak |
| Implement Flow 2 trong v1.0 | Thuộc Future scope |
