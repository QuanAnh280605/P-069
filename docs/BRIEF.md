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

Xây dựng **AI Semantic Layer Agent** — hệ thống AI hỗ trợ BA/DA xây dựng và quản lý Semantic Layer tập trung, với quy trình:

**Flow 1 (v1.0) — Generate & Manage Semantic Layer:**
1. BA/DA cung cấp Connection URL của Target DB
2. Agent tự động introspect schema kỹ thuật (SQLAlchemy Inspector — chỉ đọc metadata, không query data)
3. LLM phân tích và đề xuất tên nghiệp vụ tiếng Việt, mô tả chi tiết cho từng bảng/cột
4. LLM đề xuất Business Metrics kèm SQL template tham chiếu
5. BA/DA review, chỉnh sửa và phê duyệt qua giao diện HITL
6. Semantic Layer được lưu vào Metadata Store (PostgreSQL)
7. Export ra JSON/YAML để tích hợp với các tool BI khác

**Future Flow 2 (v2.0+) — Natural Language Query Execution:**
> Người dùng đặt câu hỏi tự nhiên → Agent dùng Semantic Layer đã xây → sinh SQL → validate → execute → trả kết quả. *Phụ thuộc vào Semantic Layer chất lượng cao từ v1.0.*

---

## 4. Phạm vi dự án (Project Scope)

### In-Scope v1.0 (Trong phạm vi):
- Tự động introspect schema từ PostgreSQL, MySQL, SQLite (chỉ đọc metadata).
- AI sinh định nghĩa tên nghiệp vụ và tự đề xuất chỉ số (metrics) kèm SQL template.
- Giao diện HITL cho phép BA/DA chỉnh sửa và phê duyệt trước khi lưu.
- CRUD đầy đủ cho Business Metrics (thêm thủ công, sửa, xóa).
- Mã hóa Connection URL (Fernet) — không lưu plaintext.
- Export Semantic Layer ra JSON / YAML.

### Out-of-Scope v1.0 (Ngoài phạm vi):
- Thực thi câu lệnh SQL trên data thực của Target DB.
- Natural Language Query (NL2SQL) → đây là v2.0+.
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
| **Schema Introspection** | SQLAlchemy Inspector |
| **Security** | `cryptography` (Fernet) — mã hóa Connection URL |
| **Export** | `pyyaml` — YAML export |
| **Frontend UI** | Next.js / Streamlit |
| **DevOps & Testing** | Docker, Docker Compose, Pytest, Ruff |

---

## 🎯 Tóm tắt mục đích trong 2 phút
> **AI Semantic Layer Agent v1.0** là công cụ **quản trị ngữ nghĩa dữ liệu doanh nghiệp có AI hỗ trợ**: AI tự động chuyển đổi tên kỹ thuật khô khan thành định nghĩa nghiệp vụ có nghĩa, tự đề xuất chỉ số kinh doanh — BA/DA chỉ cần review & duyệt thay vì gõ tay từ đầu. Kết quả là một Semantic Layer chuẩn xác, được con người phê duyệt, xuất được ra các format phổ biến để tích hợp với hệ sinh thái BI.
