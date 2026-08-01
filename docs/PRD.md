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

### Persona 1 (Primary): Alex — Business Analyst / Data Analyst
- **Mục tiêu:** Cần quản lý ngữ cảnh dữ liệu nghiệp vụ chính xác; quy định công thức tính chỉ số (doanh thu, churn rate) một lần duy nhất cho toàn đội ngũ.
- **Pain Points:** Mất thời gian trả lời lặp đi lặp lại các câu hỏi số liệu đơn giản từ các phòng ban vì mỗi người tính theo một cách riêng. Tên bảng/cột trong DB không ai nhớ được ý nghĩa.
- **Nhu cầu:** Công cụ tự động soi schema DB, đặt tên tiếng Việt có nghĩa, đề xuất metrics và có giao diện cho phép chỉnh sửa/duyệt nhanh (HITL).

### Persona 2 (Future — v2.0+): Sarah — Business Executive / Non-tech Manager
- **Mục tiêu:** Muốn đặt câu hỏi bằng ngôn ngữ tự nhiên và nhận câu trả lời dữ liệu tức thì.
- **Ghi chú:** Persona này sẽ được phục vụ bởi Flow 2 (NL2SQL Query) trong phiên bản tương lai, sử dụng Semantic Layer được xây dựng từ v1.0.

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

### Future (v2.0+) — Out of Scope cho v1.0

| Feature ID | Tên tính năng | Ghi chú |
|------------|---------------|---------|
| **F-F01** | Natural Language Query (NL2SQL) | Người dùng đặt câu hỏi tự nhiên → Agent dùng Semantic Layer sinh SQL → validate → execute → trả kết quả |
| **F-F02** | Fast Path Metric Matching | So khớp câu hỏi với Business Metric đã lưu để dùng SQL Template trực tiếp |
| **F-F03** | SQL Safety Validation | `sqlparse` kiểm tra SELECT-only, LIMIT 1000, timeout 30s |
| **F-F04** | Result Formatting | Trả kết quả dạng Text, Markdown table, KPI number |
| **F-F05** | Chart & Visualization | Sinh biểu đồ từ kết quả query |
| **F-F06** | Export Data to CSV/Excel | Tải kết quả query về máy |

---

## 4. User Stories & Tiêu chí Chấp nhận (Acceptance Criteria)

### Story 1: Tự động phân tích & đề xuất Semantic Layer
- **Là một** Business Analyst (Alex),  
- **Tôi muốn** cung cấp Connection URL của cơ sở dữ liệu và yêu cầu hệ thống tự phân tích schema,  
- **Để** tôi có bản phác thảo tên nghiệp vụ và mô tả cột mà không cần gõ tay từ đầu.
- **Tiêu chí chấp nhận:**
  - Hệ thống lấy được danh sách bảng, danh sách cột, FK và kiểu dữ liệu qua SQLAlchemy Inspector.
  - LLM trả về `business_name` tiếng Việt rõ nghĩa cho từng bảng & cột.
  - LLM đề xuất ít nhất 2-3 Business Metrics có kèm mô tả và SQL template tham chiếu.
  - Toàn bộ kết quả trả về dưới dạng Semantic Layer JSON (trạng thái `draft`, chưa lưu).

### Story 2: Review và Chỉnh sửa Semantic Layer (HITL)
- **Là một** Business Analyst (Alex),  
- **Tôi muốn** chỉnh sửa inline tên nghiệp vụ của bảng/cột và phê duyệt (hoặc từ chối) các Metric được AI gợi ý,  
- **Để** đảm bảo ngữ cảnh lưu trữ hoàn toàn chuẩn xác với thực tế công ty.
- **Tiêu chí chấp nhận:**
  - API `PUT /api/v1/semantic/{db_id}/table/{table}` và `/column/{table}/{col}` cập nhật đúng thông tin.
  - Metric bị từ chối (DELETE) không được lưu vào Metadata Store.
  - Dữ liệu sau khi chốt được lưu bền vững trong `semantic_tables`, `semantic_columns`, `semantic_metrics`.

### Story 3: Quản lý Business Metrics thủ công
- **Là một** Business Analyst (Alex),  
- **Tôi muốn** thêm, sửa, xóa Business Metric thủ công không phụ thuộc vào AI,  
- **Để** tôi có thể định nghĩa chỉ số phức tạp mà AI chưa đề xuất đúng.
- **Tiêu chí chấp nhận:**
  - API `POST /api/v1/semantic/{db_id}/metric` tạo metric mới với `name`, `description`, `sql_template`.
  - API `PUT /api/v1/semantic/{db_id}/metric/{metric_id}` cho phép chỉnh sửa.
  - API `DELETE /api/v1/semantic/{db_id}/metric/{metric_id}` xóa metric.
  - UI hiển thị danh sách metric với chức năng thêm/sửa/xóa inline.

### Story 4: Xuất Semantic Layer
- **Là một** Business Analyst (Alex),  
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

## 6. Phạm vi Không làm v1.0 (Out of Scope) & Giả định (Assumptions)

### Phạm vi Không làm trong v1.0:
- Không thực thi câu truy vấn SQL trên Target DB (chỉ đọc schema metadata).
- Không hỗ trợ Natural Language Query (NL2SQL) — đây là Flow 2 (v2.0+).
- Không hỗ trợ kết nối NoSQL databases (MongoDB, Cassandra).
- Không tự động thay đổi cấu trúc bảng (Migration) của Target DB.
- Không hiển thị data thực từ Target DB trong giao diện.

### Giả định (Assumptions):
- Target Database có thể truy cập được từ server backend (cùng network hoặc mở port/IP whitelist).
- Tài khoản DB được cung cấp có quyền truy cập `information_schema` (đọc metadata bảng/cột).
- BA/DA là người chịu trách nhiệm cuối cùng về độ chính xác của Semantic Layer đã duyệt.
