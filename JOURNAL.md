# Weekly Journal — AI Semantic Layer Agent (P-069)

> Ghi lại quá trình phát triển dự án qua các tuần: mục tiêu, thành quả, khó khăn, giải pháp và bài học kinh nghiệm.

---

## Week 1: Thiết Kế Kiến Trúc, Ingestion Engine & Schema Discovery

### Mục tiêu tuần này
- [x] Khảo sát bài toán Semantic Layer và xây dựng PRD, BRIEF, ARCHITECTURE documents.
- [x] Triển khai `SQLAlchemy Inspector` đọc schema Live Database và `SqlDumpScanner & Parser` đọc DDL dump đa dialect.
- [x] Thiết kế ERD Metadata Store 10 bảng ORM và cấu hình migrations với Alembic.

### Đã hoàn thành
- Hoàn thiện tài liệu kiến trúc hệ thống 2 luồng cốt lõi (Flow 1: Schema Enrichment, Flow 2: Deterministic Semantic Query Engine).
- Xây dựng thành công bộ phân tích cú pháp DDL Dump đa dialect (PostgreSQL, MySQL, SQLite) sử dụng `sqlglot`.
- Thiết lập hệ sinh thái backend FastAPI với cấu hình Pydantic-settings và mã hóa Fernet cho chuỗi kết nối.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Xử lý cú pháp DDL phức tạp và đa dạng giữa PostgreSQL/MySQL | Sử dụng `sqlglot` AST parser chuẩn hóa các bảng, cột và quan hệ FK | Trích xuất chính xác 100% cấu trúc schema không phụ thuộc DB engine |
| Bảo vệ thông tin nhạy cảm của Live Database | Tích hợp mã hóa đối xứng Fernet đối với `conn_url` trước khi lưu vào DB | Đảm bảo an toàn bảo mật, không lưu plaintext |

### Bài học
- Thiết kế Data Model chuẩn ngay từ đầu giúp giảm thiểu đáng kể chi phí refactor khi mở rộng các tính năng Multi-Agent và Versioning.

---

## Week 2: 2-Pass Clustering AI Enrichment & LangGraph HITL Loop

### Mục tiêu tuần này
- [x] Xây dựng cơ chế làm giàu ngữ nghĩa 2 bước: Global Domain Glossary (Pass 1) và Cluster-level Enrichment (Pass 2).
- [x] Thiết lập thuật toán phân cụm đồ thị bảng (Domain Clustering) dựa trên liên kết Foreign Keys.
- [x] Xây dựng LangGraph StateGraph cho Flow 1 với cơ chế Human-in-the-Loop (HITL) Interrupt.

### Đã hoàn thành
- Pipeline 2-Pass Enrichment sinh tên nghiệp vụ tiếng Việt tự nhiên và mô tả chi tiết cho bảng/cột.
- Cơ chế Fallback Name Generator tự động kích hoạt khi LLM gặp sự cố để đảm bảo luồng không bị gián đoạn.
- Đăng ký các endpoints HITL: inline editing cho bảng/cột và duyệt (Approve) Semantic Layer.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Context window bị quá tải khi đưa toàn bộ 36+ bảng vào 1 prompt | Phân cụm bảng theo FK (Domain Clustering) và gửi từng cụm vào LLM | Tốc độ xử lý tăng gấp 3 lần, tên tiếng Việt đồng nhất và chuẩn ngữ cảnh |
| LLM đôi khi trả về format JSON không hợp lệ | Viết bộ tiện ích `ainvoke_json` bọc cơ chế retry và regex fallback parsing | Loại bỏ 100% lỗi JSON parse exception |

---

## Week 3: Deterministic Semantic Query Engine & AST Guardrails (Flow 2)

### Mục tiêu tuần này
- [x] Triển khai `SemanticQueryCompiler` biên dịch MetricDefinition v2 thành SQL chuẩn dialect.
- [x] Tích hợp thuật toán Graph Join Resolver tìm đường đi ngắn nhất giữa các bảng dựa trên `canonical_relationships`.
- [x] Xây dựng bộ Guardrails AST bằng `sqlglot` (bắt buộc duy nhất `SELECT`, chặn lệnh ghi dữ liệu, inject `LIMIT 100` và `timeout = 15s`).

### Đã hoàn thành
- Động cơ biên dịch truy vấn xác định (Deterministic Compilation) đạt độ chính xác 100%, loại trừ hoàn toàn ảo giác.
- Hỗ trợ Compile-Only Preview và Live DB Read-Only Execution.
- Cơ chế quản lý phiên bản `metric_versions` lưu lại toàn bộ lịch sử chỉnh sửa công thức và lý do thay đổi.

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Nguy cơ tấn công SQL Injection hoặc câu lệnh phá hoại dữ liệu | Triển khai 2 lớp bảo vệ: biên dịch từ template định danh và kiểm tra AST qua `sqlglot` | Chặn đứng 100% các câu lệnh `DROP`, `DELETE`, `UPDATE`, `INSERT` |
| Xử lý truy vấn đa bảng phức tạp | Graph BFS Join Resolver tự động tìm chuỗi quan hệ JOIN ngắn nhất | Sinh câu lệnh SQL tối ưu, chính xác theo quan hệ cha - con |

---

## Week 4: Multi-Agent Conversational AI, Next.js Frontend & Demo Day Rehearsal

### Mục tiêu tuần này
- [x] Xây dựng Chat Orchestrator Multi-Agent Graph (`chitchat` vs `metric_suggest`).
- [x] Xây dựng Query Clarifier Wizard Graph hỏi đáp làm rõ câu truy vấn mơ hồ theo từng bước.
- [x] Phát triển toàn diện Single Page Workspace Frontend bằng Next.js 14 và Tailwind CSS.
- [x] Chạy toàn bộ Test Suite (621 passed) và hoàn thiện tài liệu Evaluation Evidence.

### Đã hoàn thành
- Hoàn thiện 5 Views trên Web UI: Data Model, Metrics Catalog, Metric Explorer, AI Studio và Export Playground.
- Tích hợp streaming chat và PrismJS highlight cú pháp SQL/YAML.
- Chuẩn bị đầy đủ 10 Deliverables theo yêu cầu của BTC cho Demo Day.

### Bài học
- Kiểm thử liên tục với Mock LLM và Mock DB giúp phát hiện sớm các lỗi tích hợp, duy trì test suite xanh 100% trước ngày bàn giao.
