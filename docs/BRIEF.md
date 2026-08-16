# 📄 Project Brief — AI Semantic Layer Agent

> **Tên dự án:** AI Semantic Layer Agent (P-069)  
> **Phiên bản:** 1.0.0 (Build Phase Capstone)  
> **Tổ chức:** VinUni AI20K Build Phase (Cohort 3)  

---

## 1. Vấn đề Đang Giải quyết (Problem Statement)

Trong các doanh nghiệp, dữ liệu lưu trong cơ sở dữ liệu quan hệ (PostgreSQL, MySQL, SQLite) thường gặp **2 vấn đề nghiêm trọng về ngữ nghĩa**:

1. **Khoảng cách Ngữ cảnh Nghiệp vụ (Business Context Gap):** Tên bảng/cột trong DB mang tính kỹ thuật thuần túy (`usr_tbl_01`, `amt_vat_inc`, `ord_sts_cd`) không phản ánh đúng ý nghĩa kinh doanh. Hậu quả là các phòng ban tự diễn giải theo cách riêng $\rightarrow$ tốn nhiều thời gian tra cứu Data Dictionary, dễ gây sai lệch số liệu báo cáo.
2. **Hỗn loạn Định nghĩa Chỉ số (Metric Definition Chaos):** Thiếu một "nguồn sự thật duy nhất" (Single Source of Truth) cho các công thức tính chỉ số (doanh thu thuần, conversion rate, churn rate...). Mỗi phòng ban tự tính theo cách hiểu riêng dẫn đến các báo cáo không thống nhất.

---

## 2. Đối tượng Người dùng (Target Users)

- **Primary: Business Analyst (BA) / Data Analyst (DA):** Người chịu trách nhiệm xây dựng và quản trị Semantic Layer. Cần công cụ tự động hóa phần "đặt tên nghiệp vụ" và "định nghĩa chỉ số" mà vẫn giữ quyền kiểm soát cuối cùng (HITL).
- **Secondary: Data Lead / Analytics Engineer:** Người quản lý cấu trúc quan hệ chuẩn (`canonical_relationships`), kiểm soát các phiên bản công thức chỉ số (`metric_versions`) và giám sát an toàn khi khai thác dữ liệu từ Live DB.

---

## 3. Giải pháp Đề xuất & Kiến trúc Cốt lõi (Core Solution)

Xây dựng **AI Semantic Layer Agent** — nền tảng AI Agent tập trung với **2 luồng cốt lõi (Core Pipelines)** cùng **2 đồ thị AI hội thoại thông minh**:

### Flow 1 — Generate & Manage Semantic Layer:
1. **Đa nguồn Schema Ingestion:** Kết nối Target Live DB (SQLAlchemy Inspector) hoặc upload file SQL Dump DDL (`SqlDumpScanner & Parser`).
2. **2-Pass Hierarchical & Clustering Enrichment:** Pass 1 sinh Domain Glossary $\rightarrow$ Clustering đồ thị bảng $\rightarrow$ Pass 2 sinh tên nghiệp vụ và mô tả tiếng Việt kèm Fallback.
3. **Canonical Standardization:** Tự động nhận diện Primary Key, Foreign Key, Time Dimension và `canonical_relationships`.
4. **HITL Review & Versioning:** BA/DA xem xét, chỉnh sửa inline và duyệt metrics có lưu lịch sử phiên bản (`metric_versions`).
5. **Export:** Đóng gói xuất Semantic Layer ra chuẩn JSON và YAML phục vụ tích hợp công cụ BI.

### Flow 2 — Deterministic Semantic Query Engine (CHỈ DÙNG CHO LIVE DB):
1. **Deterministic Compilation:** Người dùng chọn Metrics và Dimensions $\rightarrow$ `SemanticQueryCompiler` biên dịch thành SQL chuẩn xác 100% dựa trên quan hệ canonical.
2. **Compile Preview:** Cho phép kiểm tra câu lệnh SQL được sinh ra mà không cần chạm tới Live DB.
3. **AST Guardrails:** `sqlglot` bắt buộc duy nhất lệnh `SELECT`, tự động inject trần `LIMIT 100` (max 1000) và gán `statement_timeout = 15s`.
4. **Read-Only Execution:** Thực thi an toàn trên Live DB và trả về bảng kết quả dạng JSON.

### Conversational & Clarifier Layer:
- **Chat Orchestrator Graph (`chat_graph`):** Tự động phân loại ý định giữa trò chuyện tổng quan và sinh metric theo yêu cầu.
- **Query Clarifier Wizard (`query_clarifier`):** Hỏi đáp tương tác từng bước giúp người dùng làm rõ các câu hỏi truy vấn tự nhiên còn mơ hồ.

---

## 4. Phạm vi Dự án (Project Scope)

### In-Scope v1.0:
- Introspect schema từ PostgreSQL, MySQL, SQLite.
- Quét và phân tích AST file SQL Dump DDL cho PostgreSQL, MySQL, SQLite kèm Technical Preview.
- 2-Pass AI Schema Enrichment và đề xuất Business Metrics.
- Giao diện Web Next.js 14 với 5 Tab Views chuyên biệt.
- Quản trị vòng đời metric, trạng thái duyệt (Approve) và lưu vết lịch sử phiên bản (`metric_versions`).
- Mã hóa chuỗi kết nối Target DB bằng Fernet đối xứng.
- Biên dịch truy vấn dữ liệu Semantic Query và thực thi an toàn Read-Only trên Live DB kèm AST Guardrails.
- Xuất Semantic Layer ra file JSON và YAML.

### Out-of-Scope v1.0:
- Truy vấn dữ liệu thực tế trên file SQL Dump (do SQL Dump chỉ chứa DDL cấu trúc, không có runtime DB).
- Text-to-SQL tự do qua LLM (thay vào đó dùng Deterministic Semantic Query Engine để đảm bảo chính xác 100%).
- Các câu lệnh SQL thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
- Kết nối cơ sở dữ liệu NoSQL (MongoDB, Cassandra).

---

## 5. Công nghệ Sử dụng (Tech Stack)

| Tầng / Thành phần | Công nghệ |
|---|---|
| **Core Architecture** | Python 3.11, LangGraph, LangChain |
| **LLM Provider** | OpenAI GPT-4o-mini (`temperature = 0.0`) |
| **API Gateway** | FastAPI, Uvicorn (Async IO REST API) |
| **Metadata Store** | PostgreSQL (10 ORM Models + Alembic Migrations) / SQLite |
| **SQL Parser & Guardrails** | `sqlglot` (AST Validation & Query Safety) |
| **Security & Auth** | `cryptography` (Fernet), `python-jose` (JWT), `passlib` (Bcrypt) |
| **Frontend Web App** | Next.js 14 (App Router), Tailwind CSS, Lucide Icons, PrismJS |
| **DevOps & Testing** | Docker, Docker Compose, Pytest, Ruff |

---

## 🎯 Tóm tắt Giá trị trong 2 phút
> **AI Semantic Layer Agent** là nền tảng **quản trị và khai thác ngữ nghĩa dữ liệu doanh nghiệp có AI hỗ trợ toàn diện**: Tự động chuyển đổi technical schema khô khan thành định nghĩa kinh doanh rõ ràng bằng tiếng Việt, thiết lập Single Source of Truth cho Business Metrics có quản lý lịch sử phiên bản, đồng thời cung cấp công cụ **truy vấn dữ liệu an toàn và chuẩn xác trên Live Database** được bảo vệ bởi hệ thống AST Guardrails nghiêm ngặt.
