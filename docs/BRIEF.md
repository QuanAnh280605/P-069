# 📄 Project Brief — AI Semantic Layer Agent

> **Tên dự án:** AI Semantic Layer Agent  
> **Phiên bản:** 1.0.0  
> **Loại dự án:** Capstone Project / VinUni AI20K Build Phase  

---

## 1. Vấn đề đang giải quyết (Problem Statement)

Trong các doanh nghiệp, dữ liệu lưu trong database quan hệ (PostgreSQL, MySQL, SQLite) gặp phải **2 vấn đề nghiêm trọng về ngữ nghĩa**:

1. **Mất ngữ cảnh nghiệp vụ (Business Context Gap):** Tên bảng/cột trong DB mang tính kỹ thuật thuần túy (`usr_tbl_01`, `amt_vat_inc`, `ord_sts_cd`) không phản ánh đúng ý nghĩa nghiệp vụ. Hậu quả là mỗi phòng ban tự diễn giải theo cách riêng → số liệu báo cáo không khớp nhau, mất thời gian giải thích lẫn nhau.

2. **Thiếu định nghĩa chỉ số thống nhất (Metric Definition Chaos):** Không có nơi nào là "nguồn sự thật duy nhất" cho công thức tính doanh thu, churn rate, conversion rate... Mỗi team/analyst tự tính theo cách hiểu riêng → cùng một câu hỏi kinh doanh có nhiều đáp án khác nhau.

**Hiện tại, giải pháp thủ công gặp vấn đề:**
- BA/DA phải tự ngồi viết tài liệu Data Dictionary bằng tay → tốn hàng tuần, nhanh lỗi thời
- Tài liệu lưu rải rác trên Confluence/Google Docs → không ai cập nhật, không tích hợp được với tool

---

## 2. Đối tượng người dùng (Target Users)

- **Primary: Business Analyst (BA) / Data Analyst (DA):** Người chịu trách nhiệm xây dựng và quản trị Semantic Layer. Cần công cụ giúp tự động hóa phần "đặt tên nghiệp vụ" và "định nghĩa chỉ số" mà vẫn giữ quyền kiểm soát cuối cùng.

- **Future (v2.0+): Nhà quản lý & Nhân viên nghiệp vụ (Non-technical Users):** Sẽ hưởng lợi từ Semantic Layer đã được xây dựng ở v1.0 khi Flow 2 (NL2SQL Query) được phát triển.

---

## 3. Giải pháp đề xuất (Proposed Solution)

Xây dựng **AI Semantic Layer Agent** — hệ thống AI hỗ trợ BA/DA xây dựng, quản lý và khai thác Semantic Layer tập trung, với 2 luồng chính:

**Flow 1 — Generate & Manage Semantic Layer:**
1. BA/DA cung cấp Connection URL của Target DB (hoặc upload SQL Dump)
2. Agent tự động introspect schema kỹ thuật (SQLAlchemy Inspector — đọc metadata)
3. LLM phân tích và đề xuất tên nghiệp vụ tiếng Việt, mô tả chi tiết cho từng bảng/cột
4. LLM đề xuất Business Metrics kèm SQL template tham chiếu
5. BA/DA review, chỉnh sửa và phê duyệt qua giao diện HITL
6. Semantic Layer được lưu vào Metadata Store (PostgreSQL)
7. Export ra JSON/YAML để tích hợp với các tool BI khác

**Flow 2 — Semantic Layer Query Engine (Live DB Only):**
1. User chọn các Business Metrics, Dimensions và Filters trên giao diện Metric Explorer
2. `SemanticQueryCompiler` tự động biên dịch cấu hình đã chọn thành câu lệnh SQL chuẩn xác 100% dựa trên định nghĩa đã duyệt
3. `SQLGuardrailNode` ép các điều kiện an toàn (Read-Only `SELECT`, auto `LIMIT 100`, `timeout = 15s`)
4. Thực thi truy vấn dữ liệu thực tế trên Target Live DB và hiển thị bảng kết quả

---

## 4. Phạm vi dự án (Project Scope)

### In-Scope v1.0 (Trong phạm vi):
- Tự động introspect schema từ PostgreSQL, MySQL, SQLite (đọc metadata).
- Parse file SQL Dump DDL cho PostgreSQL và MySQL.
- AI sinh định nghĩa tên nghiệp vụ và tự đề xuất chỉ số (metrics) kèm SQL template.
- Giao diện HITL cho phép BA/DA chỉnh sửa và phê duyệt trước khi lưu.
- CRUD đầy đủ cho Business Metrics (thêm thủ công, sửa, xóa).
- Mã hóa Connection URL (Fernet) — không lưu plaintext.
- Export Semantic Layer ra JSON / YAML.
- **Truy vấn dữ liệu qua Semantic Layer (`SemanticQueryCompiler`) áp dụng CHỈ cho Target DB kết nối qua Connection String (Live DB) với các Guardrails Read-Only an toàn.**

### Out-of-Scope v1.0 (Ngoài phạm vi):
- Truy vấn dữ liệu trực tiếp trên file SQL Dump (do SQL Dump chỉ chứa DDL cấu trúc, không có runtime DB).
- Natural Language Query (NL2SQL) tự do qua LLM (thay vào đó dùng Deterministic Semantic Layer Query Engine để đảm bảo độ chính xác).
- Các câu lệnh SQL làm thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`).
- Truy vấn liên cơ sở dữ liệu (Cross-database join).
- Fine-tune model LLM riêng (dùng GPT-4o-mini qua API).
- Kết nối NoSQL (MongoDB, Cassandra).

---

## 5. Công nghệ dự kiến sử dụng (Tech Stack)

| Thành phần | Công nghệ chọn lựa |
|------------|-------------------|
| **Core Architecture** | Python 3.11, LangGraph, LangChain |
| **LLM Provider** | OpenAI GPT-4o-mini (Temperature `0.0`) |
| **API Gateway** | FastAPI, Uvicorn (Async IO) |
| **Metadata Store** | PostgreSQL (SQLAlchemy ORM + Alembic migrations) |
| **Schema Introspection** | SQLAlchemy Inspector / sqlglot |
| **Query Engine & AST** | `sqlglot` (SQL AST Validation & Guardrails) |
| **Security** | `cryptography` (Fernet) — mã hóa Connection URL |
| **Export** | `pyyaml` — YAML export |
| **Frontend UI** | Next.js |
| **DevOps & Testing** | Docker, Docker Compose, Pytest, Ruff |

---

## 🎯 Tóm tắt mục đích trong 2 phút
> **AI Semantic Layer Agent v1.0** là công cụ **quản trị và khai thác ngữ nghĩa dữ liệu doanh nghiệp có AI hỗ trợ**: AI tự động chuyển đổi tên kỹ thuật khô khan thành định nghĩa nghiệp vụ có nghĩa, tự đề xuất chỉ số kinh doanh — BA/DA review & duyệt. Sau đó, người dùng có thể **truy vấn dữ liệu an toàn và chuẩn xác trên Live DB** thông qua bộ định nghĩa Semantic Layer đã chốt.

