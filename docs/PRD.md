# 📑 Product Requirements Document (PRD) — AI Semantic Layer Agent

> **Product Name:** AI Semantic Layer Agent  
> **Status:** Draft / Active  
> **Target Release:** v1.0.0 (Build Phase Capstone)  
> **Author:** Antigravity AI & Engineering Team  

---

## 1. Mục tiêu Sản phẩm (Product Goals)

1. **Chuẩn hóa Semantic Layer doanh nghiệp (Unified Semantic Layer):** AI tự động phân tích schema kỹ thuật của database (tên bảng/cột dạng `usr_tbl_01`, `amt_vat_inc`) và sinh ra lớp định nghĩa nghiệp vụ thống nhất (tên tiếng Việt rõ nghĩa, mô tả chi tiết) để toàn bộ đội ngũ dùng chung một ngôn ngữ.
2. **Quản lý Business Metrics tập trung (Single Source of Truth for Metrics):** Cung cấp một nơi duy nhất để BA/DA định nghĩa chính thức công thức tính các chỉ số kinh doanh (doanh thu, churn rate, ARPU...) kèm SQL template tham chiếu, tránh mỗi phòng ban tính mỗi kiểu.
3. **HITL Governance — Con người làm chủ định nghĩa:** Mọi định nghĩa do AI đề xuất đều phải qua bước review & duyệt của BA/DA trước khi có hiệu lực chính thức, đảm bảo độ tin cậy và trách nhiệm giải trình.

---

## 2. Đối tượng Người dùng & Chân dung (User Personas)

### Persona 1 (Primary): Business Analyst / Data Analyst
- **Mục tiêu:** Cần quản lý ngữ cảnh dữ liệu nghiệp vụ chính xác; quy định công thức tính chỉ số (doanh thu, churn rate) một lần duy nhất cho toàn đội ngũ.
- **Pain Points:** Mất thời gian trả lời lặp đi lặp lại các câu hỏi số liệu đơn giản từ các phòng ban vì mỗi người tính theo một cách riêng. Tên bảng/cột trong DB không ai nhớ được ý nghĩa.
- **Nhu cầu:** Công cụ tự động soi schema DB, đặt tên tiếng Việt có nghĩa, đề xuất metrics và có giao diện cho phép chỉnh sửa/duyệt nhanh (HITL).

---

## 3. Danh sách Tính năng & Mức độ Ưu tiên (Feature List & Priority)

### v1.0 — In Scope

| Feature ID | Tên tính năng | Mô tả chi tiết | Mức ưu tiên |
|------------|---------------|----------------|-------------|
| **F-01** | Database Schema Introspection | Tự động kết nối Target DB (Postgres/MySQL/SQLite), dùng SQLAlchemy Inspector lấy tên bảng, cột, kiểu dữ liệu, khóa ngoại và giá trị mẫu. **Chỉ đọc schema metadata — không thực thi query data.** | **P0 (Must-Have)** |
| **F-02** | LLM Business Name Enrichment | AI phân tích tên bảng/cột kỹ thuật và sinh tên nghiệp vụ (`business_name`) tiếng Việt rõ nghĩa kèm mô tả chi tiết cho từng bảng và cột. | **P0 (Must-Have)** |
| **F-03** | Business Metric Suggestion | AI phân tích cấu trúc bảng/cột để tự động đề xuất chỉ số kinh doanh (VD: "Tổng doanh thu", "Tỷ lệ chuyển đổi đơn hàng") kèm SQL template tham chiếu. | **P0 (Must-Have)** |
| **F-04** | HITL Review & Editing | Giao diện/API cho phép BA/DA xem lại toàn bộ draft AI đề xuất, chỉnh sửa inline tên nghiệp vụ, mô tả cột và duyệt/từ chối/chỉnh sửa các Business Metrics trước khi lưu chính thức. | **P0 (Must-Have)** |
| **F-05** | Metadata Store Persistence | Lưu trữ Semantic Layer hoàn chỉnh (sau khi được BA/DA duyệt) vào PostgreSQL metadata store. Hỗ trợ CRUD đầy đủ cho table, column, metric. | **P0 (Must-Have)** |
| **F-06** | Manual Metric Management | Cho phép BA/DA thêm thủ công Business Metric mới (không cần qua LLM), chỉnh sửa, xóa metric đã có trong Library. | **P0 (Must-Have)** |
| **F-07** | Export Semantic Layer | Xuất Semantic Layer đã duyệt ra file **JSON** hoặc **YAML** để tích hợp với các công cụ BI khác (Metabase, dbt, Looker Studio). | **P1 (Should-Have)** |
| **F-08** | Connection URL Encryption | Mã hóa Connection URL của Target DB bằng Fernet trước khi lưu vào Metadata Store. Không bao giờ lưu plaintext. | **P0 (Must-Have)** |
| **F-09** | Import Schema Dump | Cho phép BA/DA upload file SQL dump (`.sql`) hoặc schema definition để hệ thống parse schema metadata mà **không cần kết nối live DB**. Hỗ trợ PostgreSQL dump (`pg_dump --schema-only`) và MySQL dump. | **P1 (Should-Have)** |

---

## 4. User Stories & Tiêu chí Chấp nhận (Acceptance Criteria)

### Story 1: Tự động phân tích & đề xuất Semantic Layer
- **Là một** Business Analyst,  
- **Tôi muốn** cung cấp Connection URL của cơ sở dữ liệu và yêu cầu hệ thống tự phân tích schema,  
- **Để** tôi có bản phác thảo tên nghiệp vụ và mô tả cột mà không cần gõ tay từ đầu.
- **Tiêu chí chấp nhận:**
  - Hệ thống lấy được danh sách bảng, danh sách cột, FK và kiểu dữ liệu qua SQLAlchemy Inspector.
  - LLM trả về `business_name` tiếng Việt rõ nghĩa cho từng bảng & cột.
  - LLM đề xuất ít nhất 2-3 Business Metrics có kèm mô tả và SQL template tham chiếu.
  - Toàn bộ kết quả trả về dưới dạng Semantic Layer JSON (trạng thái `draft`, chưa lưu).

### Story 2: Review và Chỉnh sửa Semantic Layer (HITL)
- **Là một** Business Analyst,  
- **Tôi muốn** chỉnh sửa inline tên nghiệp vụ của bảng/cột và phê duyệt (hoặc từ chối) các Metric được AI gợi ý,  
- **Để** đảm bảo ngữ cảnh lưu trữ hoàn toàn chuẩn xác với thực tế công ty.
- **Tiêu chí chấp nhận:**
  - API `PUT /api/v1/semantic/{db_id}/table/{table}` và `/column/{table}/{col}` cập nhật đúng thông tin.
  - Metric bị từ chối (DELETE) không được lưu vào Metadata Store.
  - Dữ liệu sau khi chốt được lưu bền vững trong `semantic_tables`, `semantic_columns`, `semantic_metrics`.

### Story 3: Quản lý Business Metrics thủ công
- **Là một** Business Analyst,  
- **Tôi muốn** thêm, sửa, xóa Business Metric thủ công không phụ thuộc vào AI,  
- **Để** tôi có thể định nghĩa chỉ số phức tạp mà AI chưa đề xuất đúng.
- **Tiêu chí chấp nhận:**
  - API `POST /api/v1/semantic/{db_id}/metric` tạo metric mới với `name`, `description`, `sql_template`.
  - API `PUT /api/v1/semantic/{db_id}/metric/{metric_id}` cho phép chỉnh sửa.
  - API `DELETE /api/v1/semantic/{db_id}/metric/{metric_id}` xóa metric.
  - UI hiển thị danh sách metric với chức năng thêm/sửa/xóa inline.

### Story 4: Xuất Semantic Layer
- **Là một** Business Analyst,  
- **Tôi muốn** xuất Semantic Layer của một database ra file JSON hoặc YAML,  
- **Để** tích hợp định nghĩa nghiệp vụ vào Metabase, dbt hoặc chia sẻ với các team khác.
- **Tiêu chí chấp nhận:**
  - `GET /api/v1/semantic/{db_id}/export?format=json` trả về file download dạng JSON.
  - `GET /api/v1/semantic/{db_id}/export?format=yaml` trả về file download dạng YAML.
  - File export bao gồm đầy đủ: thông tin DB, danh sách bảng, cột với business_name & description, danh sách metrics với sql_template.

### Story 5: Bảo mật Connection URL
- **Là một** Database Administrator (Dave),  
- **Tôi muốn** Connection URL không bao giờ được lưu dưới dạng plaintext,  
- **Để** bảo vệ thông tin xác thực DB trong trường hợp Metadata Store bị truy cập trái phép.
- **Tiêu chí chấp nhận:**
  - Connection URL được mã hóa Fernet trước khi INSERT vào `semantic_databases.conn_url_enc`.
  - Khi cần introspect lại, hệ thống decrypt trong memory, không log ra plaintext.

### Story 6: Import Schema từ file SQL Dump
- **Là một** Business Analyst,  
- **Tôi muốn** upload file SQL dump (`.sql`) của database thay vì cung cấp live Connection URL,  
- **Để** tôi có thể phân tích schema của DB production mà không cần mở kết nối trực tiếp hoặc khi không có quyền truy cập live DB.
- **Tiêu chí chấp nhận:**
  - API `POST /api/v1/semantic/import-dump` nhận file `.sql` upload (multipart/form-data).
  - Hệ thống parse DDL statements (`CREATE TABLE`, `ALTER TABLE ADD CONSTRAINT`) từ file dump để extract tên bảng, cột, kiểu dữ liệu, FK — **không thực thi SQL**.
  - Sau khi parse thành công, pipeline tiếp tục từ bước Enrich Node (LLM đặt tên nghiệp vụ) giống Flow 1 thông thường.
  - Hỗ trợ format: PostgreSQL dump (`pg_dump --schema-only`) và MySQL dump (`mysqldump --no-data`).
  - Trả về lỗi rõ ràng nếu file không phải SQL dump hợp lệ hoặc không có DDL statement nào.

---

## 5. Yêu cầu Phi chức năng (Non-functional Requirements)

### 5.1. Bảo mật (Security)
- **Encryption:** Connection URL của Target DB bắt buộc được mã hóa Fernet trước khi lưu.
- **Schema-Only Access:** Kết nối Target DB chỉ dùng `SQLAlchemy Inspector` để đọc schema metadata — **không thực thi câu lệnh trên data thực.**
- **API Key Handling:** `OPENAI_API_KEY` quản lý qua `.env`, tuyệt đối không commit.

### 5.2. Độ tin cậy & Xử lý Lỗi (Reliability & Error Handling)
- **Deterministic LLM Output:** `LLM_TEMPERATURE=0.0` áp dụng cho tất cả các node.
- **Graceful DB Error:** Nếu Connection URL sai hoặc DB không truy cập được, trả về lỗi rõ ràng (`ConnectionError`) với hướng dẫn khắc phục, không crash server.
- **Partial Introspection:** Nếu một bảng lỗi quyền truy cập, bỏ qua bảng đó và tiếp tục xử lý các bảng còn lại.

### 5.3. Hiệu năng (Performance)
- Schema Introspection + LLM Enrichment cho DB ≤ 20 bảng: hoàn thành trong **< 60 giây**.
- API CRUD (update business_name, add metric): phản hồi trong **< 500ms**.

---
