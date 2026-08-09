# 📋 Kế hoạch Hành động (Action Plan) — Căn chỉnh AI Semantic Layer

> **Scope chính thức của v1.0** được xác định bởi `AGENTS.md`, `PRD.md` và `ARCHITECTURE.md`.
> **Flow 1:** Generate & Manage Semantic Layer (Live DB / SQL Dump).
> **Flow 2:** Semantic Layer Query Engine (CHỈ DÙNG CHO CONNECTION STRING / LIVE DB).

---

## 1. Kế hoạch Phát triển Flow 2 — Semantic Layer Query Engine

### 1.1. Mục tiêu & Nguyên lý Hoạt động
- **Không dùng Text-to-SQL tự do:** Tránh rủi ro ảo giác (hallucination) của LLM và lỗi cú pháp.
- **Biên dịch Chuẩn hóa (Deterministic Compilation):** Người dùng chọn Metrics + Dimensions + Filters từ UI Metric Explorer $\rightarrow$ `SemanticQueryCompiler` sử dụng `sql_template` và mối quan hệ giữa các bảng (Joins) đã duyệt ở Flow 1 để tạo câu lệnh SQL 100% chuẩn xác.
- **Chỉ áp dụng cho Live DB:** Cần kết nối tới Target DB thực tế thông qua Connection String. *SQL Dump file chỉ chứa DDL cấu trúc nên không áp dụng Flow 2.*

### 1.2. Các Bước Triển Khai (Task List)
- [x] **Cập nhật Tài liệu:** Đồng bộ Scope Flow 2 vào `AGENTS.md`, `ARCHITECTURE.md`, `PRD.md`, `BRIEF.md`.
- [ ] **Phát triển Core Service `SemanticQueryCompiler`:**
  - Map Metric IDs với `sql_template` đã lưu trong Metadata Store.
  - Xử lý câu lệnh `JOIN` tự động dựa trên quan hệ Foreign Key (`semantic_columns` / `relationships`).
  - Generate ra SQL String hoàn chỉnh.
- [ ] **Phát triển Node Security `SQLGuardrailNode` (dùng `sqlglot`):**
  - Kiểm tra AST: Ép duy nhất lệnh `SELECT` (chặn `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
  - Tự động inject `LIMIT 100` (hoặc tối đa 1000 rows).
  - Cài đặt `statement_timeout = 15s`.
- [ ] **Phát triển API Endpoint:**
  - Route: `POST /api/v1/semantic/query`
  - Validation: Kiểm tra nguồn DB. Nếu là SQL Dump $\rightarrow$ Trả lỗi HTTP 400 rõ ràng.
- [ ] **Xây dựng Giao diện Frontend (Metric Explorer):**
  - Màn hình cho phép chọn Metric, Dimension và Filter.
  - Nút "Chạy truy vấn" và Bảng kết quả dữ liệu (Data Table / JSON Viewer).

---

## 2. Các Đầu Việc Tích hợp & Kiểm thử

### EPIC 1: Backend Services
- **Task 1.1:** Hoàn thiện `SemanticQueryCompiler` trong `src/services/query_compiler.py`.
- **Task 1.2:** Hoàn thiện Guardrail Validator trong `src/services/sql_guardrails.py`.
- **Task 1.3:** Đăng ký API route `POST /api/v1/semantic/query` trong `src/api/routes.py`.

### EPIC 2: Frontend Metric Explorer
- **Task 2.1:** Tạo Component Metric Explorer trong Next.js frontend (`frontend/src/components/MetricExplorer.tsx`).
- **Task 2.2:** Tích hợp gọi API `POST /api/v1/semantic/query` và hiển thị kết quả truy vấn.
- **Task 2.3:** Thêm trạng thái khóa/disabled tính năng Query khi nguồn là SQL Dump.

### EPIC 3: Testing & Quality Assurance
- **Task 3.1:** Unit test cho `SemanticQueryCompiler` trong `tests/test_services/test_query_compiler.py`.
- **Task 3.2:** Unit test cho Guardrails (bẫy các câu SQL độc hại, kiểm tra inject LIMIT) trong `tests/test_services/test_sql_guardrails.py`.
- **Task 3.3:** Integration test cho API `POST /api/v1/semantic/query`.

