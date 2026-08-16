# 📑 ĐẶC TẢ TÍNH NĂNG / FEATURE SPECIFICATIONS — P-069

Tài liệu quy định chi tiết các Bản Đặc tả Tính năng (Feature Specifications) chuẩn mực cho hệ thống **AI Semantic Layer Agent (P-069)**.

---

## ĐẶC TẢ #1: 2-Pass Hierarchical & Clustering Schema Enrichment

| Thuộc tính | Chi tiết |
|---|---|
| **Mã Tính năng** | `[F-03]` / `[US-001]` |
| **Tên tính năng** | **2-Pass Hierarchical & Clustering AI Schema Enrichment** |
| **Mô-đun chịu trách nhiệm** | `src/services/pass1_global_glossary.py`, `src/services/clustering.py`, `src/services/pass2_cluster_enrichment.py`, `src/agents/nodes/enrich_node.py` |
| **Trạng thái** | **Đã hiện thực & Hoạt động** |

### 1. Động lực & Bài toán
Khi xử lý các cơ sở dữ liệu lớn (> 20-50 bảng), việc gửi toàn bộ schema vào một prompt phẳng duy nhất của LLM dẫn đến vượt quá Context Window, thiếu tính nhất quán về mặt thuật ngữ và tốn kém chi phí token.

### 2. Thiết kế Giải pháp
1. **Pass 1 — Global Domain Glossary (`pass1_global_glossary.py`):** LLM quét nhanh toàn bộ danh sách bảng và cột để rút trích bảng chú giải thuật ngữ miền nghiệp vụ cốt lõi (Domain Dictionary).
2. **Domain/Graph Clustering (`clustering.py`):** Phân nhóm các bảng thành các cụm mạch lạc theo đồ thị liên kết khóa ngoại (Foreign Keys) hoặc theo ngữ nghĩa tên bảng.
3. **Pass 2 — Cluster-Level Schema Enrichment (`pass2_cluster_enrichment.py`):** Xử lý song song từng cụm bảng với ngữ cảnh từ điển thu được từ Pass 1 để sinh `business_name` và `description` tiếng Việt chuẩn xác.
4. **Fallback Mechanism:** Nếu LLM gặp lỗi cú pháp JSON hoặc timeout, hệ thống tự động kích hoạt bộ sinh tên quy chuẩn (`_fallback_enrichment`) đảm bảo pipeline không bị gián đoạn.

---

## ĐẶC TẢ #2: SQL Dump Scanner, Parser & Technical Preview with Diagnostics

| Thuộc tính | Chi tiết |
|---|---|
| **Mã Tính năng** | `[F-02]` / `[US-006]` |
| **Tên tính năng** | **SQL Dump Scanner & AST Parser with Technical Preview & Diagnostics** |
| **Mô-đun chịu trách nhiệm** | `src/services/sql_dump_scanner.py`, `src/services/sql_dump_parser.py`, `src/services/schema_ingestion.py` |
| **Trạng thái** | **Đã hiện thực & Hoạt động** |

### 1. Động lực & Bài toán
Người dùng muốn phân tích schema của hệ thống Production nhưng không thể mở kết nối trực tiếp Live DB do chính sách bảo mật mạng của doanh nghiệp.

### 2. Thiết kế Giải pháp
1. **Đa Dialect AST Parsing:** Phân tích cú pháp DDL statements (`CREATE TABLE`, `ALTER TABLE`, `ADD CONSTRAINT`) cho PostgreSQL (`pg_dump`), MySQL (`mysqldump`) và SQLite bằng bộ parser chuyên dụng.
2. **Technical Preview & Diagnostics:** Trả về đối tượng `SqlDumpPreviewResponse` gồm danh sách bảng, cột, kiểu dữ liệu, khóa ngoại được nhận diện kèm mã chẩn đoán (`DiagnosticCode`) và cảnh báo lỗi cú pháp.
3. **Persisted Dump Schema:** Cho phép lưu Technical Schema đã parse vào bảng `imported_schemas` để tái sử dụng mà không cần upload lại file.

---

## ĐẶC TẢ #3: Deterministic Semantic Query Compiler with Guardrails & Live Execution

| Thuộc tính | Chi tiết |
|---|---|
| **Mã Tính năng** | `[F-08]`, `[F-09]` / `[US-007]` |
| **Tên tính năng** | **Deterministic Semantic Query Compiler with AST Guardrails & Live Execution** |
| **Mô-đun chịu trách nhiệm** | `src/services/query_compiler.py`, `src/services/metric_definition_resolver.py`, `src/services/query_execution.py` |
| **Trạng thái** | **Đã hiện thực & Hoạt động** |

### 1. Động lực & Bài toán
Loại bỏ hoàn toàn rủi ro ảo giác (hallucination) và sai lệch công thức của Text-to-SQL tự do khi khai thác dữ liệu kinh doanh thực tế.

### 2. Thiết kế Giải pháp
1. **Deterministic Compilation:** `SemanticQueryCompiler` tiếp nhận danh sách Metric IDs, Dimension columns, Time Grains và Dimension Filters $\rightarrow$ Sử dụng `MetricDefinition` v2 và `CanonicalRelationshipModel` để tự động xây dựng câu lệnh SQL chuẩn xác cùng các mệnh đề `JOIN`, `GROUP BY`, `WHERE`.
2. **Compile-Only Preview API:** Endpoint `POST /api/v1/semantic/{db_id}/query/compile` cho phép xem trước câu lệnh SQL và các thông tin chẩn đoán mà không cần thực thi trên DB đích.
3. **Double AST Guardrails:** Sử dụng `sqlglot` kiểm tra cây cú pháp AST:
   - Bắt buộc câu lệnh là duy nhất `SELECT` (chặn tuyệt đối `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
   - Tự động gán trần `LIMIT 100` (tối đa 1000).
   - Thiết lập `statement_timeout = 15s` chống treo DB.
4. **Live Execution:** Giải mã chuỗi kết nối Fernet trong RAM và thực thi an toàn trên Live Database, trả về bảng dữ liệu và thời gian thực thi.

---

## ĐẶC TẢ #4: Metric Definition Lifecycle, Versioning & Audit History

| Thuộc tính | Chi tiết |
|---|---|
| **Mã Tính năng** | `[F-05]`, `[F-07]` / `[US-003]` |
| **Tên tính năng** | **Metric Definition Lifecycle, Versioning & Audit History** |
| **Mô-đun chịu trách nhiệm** | `src/models/metric_definition.py`, `src/services/metric_definitions.py`, `src/services/semantic_service.py` |
| **Trạng thái** | **Đã hiện thực & Hoạt động** |

### 1. Động lực & Bài toán
Tránh tình trạng "mỗi người tính một kiểu" và cần kiểm soát chặt chẽ ai đã thay đổi công thức chỉ số, thay đổi khi nào và vì lý do gì.

### 2. Thiết kế Giải pháp
1. **Cấu trúc `MetricDefinition` v2:** Quản lý chỉ số có cấu trúc: Tên, Mô tả, Base Entity, Aggregation Type (`SUM`, `COUNT`, `AVG`...), Expression/Formula, Dimensions hỗ trợ và Fixed Filters.
2. **Quản lý Nguồn & Trạng thái Phê duyệt:** Phân biệt chỉ số do AI sinh (`source: 'ai'`) hay do người dùng tạo (`source: 'manual'`), cùng trạng thái phê duyệt (`approved_by`, `status: 'active'`).
3. **Tự động Lưu vết Phiên bản (`metric_versions`):** Mỗi khi BA/DA chỉnh sửa công thức qua API `PUT`, hệ thống tự động tăng trường `version` và ghi nhận một bản ghi mới vào bảng `metric_versions` kèm lý do thay đổi (`change_reason`).
4. **History Drawer:** Giao diện cho phép xem lại toàn bộ dòng thời gian các phiên bản công thức cũ của metric.

---

## ĐẶC TẢ #5: Multi-Agent Conversational Studio & Query Clarifier Wizard

| Thuộc tính | Chi tiết |
|---|---|
| **Mã Tính năng** | `[F-10]`, `[F-11]` / `[US-008]` |
| **Tên tính năng** | **Multi-Agent Conversational Studio & Multi-turn Query Clarifier Wizard** |
| **Mô-đun chịu trách nhiệm** | `src/agents/chat_graph.py`, `src/agents/nodes/orchestrator_node.py`, `src/agents/query_clarifier/graph.py`, `src/api/query_clarify_routes.py` |
| **Trạng thái** | **Đã hiện thực & Hoạt động** |

### 1. Động lực & Bài toán
Người dùng không chuyên về kỹ thuật (Business Users) thường đưa ra các câu hỏi ngôn ngữ tự nhiên chưa rõ ràng (ví dụ: "Cho tôi xem doanh số năm nay" mà không nói rõ doanh số theo cửa hàng hay sản phẩm).

### 2. Thiết kế Giải pháp
1. **Chat Orchestrator Multi-Agent Graph (`chat_graph.py`):**
   - `orchestrator_node`: Phân tích ý định của người dùng bằng LLM.
   - Nếu là chào hỏi/hỏi đáp tổng quan $\rightarrow$ Chuyển tiếp tới `chitchat_node`.
   - Nếu là yêu cầu định nghĩa chỉ số kinh doanh $\rightarrow$ Chuyển tiếp tới `on_demand_metric_suggest_node` sinh cấu trúc `MetricDefinition` và mẫu SQL.
2. **Query Clarifier Wizard Graph (`query_clarifier/graph.py`):**
   - `wizard_init_node`: Phân tích câu hỏi tự nhiên ban đầu, đối chiếu với danh mục Catalog Semantic Layer để tìm các điểm còn mơ hồ.
   - `wizard_step_node`: Tương tác từng bước hỏi người dùng chọn các chiều phân tích (Dimension) và bộ lọc (Filter) phù hợp.
   - `resolve_node`: Đóng gói cấu hình đã làm rõ thành Semantic Query hợp lệ và chuyển tiếp sang Metric Explorer để thực thi.
