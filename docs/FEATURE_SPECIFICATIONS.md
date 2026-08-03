# 📑 ĐẶC TẢ TÍNH NĂNG / FEATURE SPECIFICATION — P-069 MVP

Tài liệu này quy định chi tiết các Đặc tả tính năng (Feature Specification) theo đúng chuẩn mực phát triển phần mềm cho dự án **P-069: AI Semantic Layer Agent (v1.0 MVP)**.

---

## ĐẶC TẢ #1

| Trường thông tin | Giá trị |
|---|---|
| **Mã User Story liên quan** | `[US-001]` / `[F-02]` |
| **Tên tính năng** | **LLM Business Name Enrichment (Tự động Chuẩn hóa Tên Nghiệp vụ & Mô tả Tiếng Việt)** |
| **Người viết** | Đội ngũ Phát triển P-069 (Dev A & Lead) |
| **Ngày tạo** | 03/08/2026 |
| **Ngày cập nhật gần nhất** | 03/08/2026 |
| **Trạng thái** | **Đã duyệt** |

---

### 1. ĐỘNG LỰC (MOTIVATION)

* **Vấn đề cần giải quyết:**  
  Các cơ sở dữ liệu quan hệ thực tế trong doanh nghiệp thường đặt tên bảng/cột bị mã hóa hoặc viết tắt kỹ thuật (ví dụ: `usr_tbl_01`, `amt_vat_inc`, `stat_flg`). Điều này khiến Business Analyst (BA) và Data Analyst (DA) phải tốn hàng tuần nhập liệu thủ công Từ điển dữ liệu (Data Dictionary), dễ gây hiểu nhầm số liệu giữa các phòng ban.
* **Người dùng mục tiêu:**  
  Business Analyst (BA), Data Analyst (DA) và Data Engineer (DE). Hiện tại họ phải gõ tay từng tên tiếng Việt và mô tả cho hàng trăm cột DB bằng Excel/Google Sheets.
* **Mục tiêu kỳ vọng:**  
  - Tự động hóa 90% việc đặt tên nghiệp vụ tiếng Việt và sinh mô tả cho toàn bộ bảng/cột trong Target DB.  
  - Thời gian xử lý cho database 20 bảng: $< 15$ giây.  
  - 100% output sinh ra là tiếng Việt chuẩn từ vựng doanh nghiệp.
* **Phương án thay thế đã xem xét:**  
  - *Phương án 1 (Viết quy tắc Regex / Map cứng từ điển):* Không linh hoạt, không hiểu được ngữ cảnh các tên bảng kỳ dị do dev đặt.  
  - *Chọn phương án:* **Dùng LLM (`temperature=0.0`) kết hợp Prompt Engineering & Few-shot learning** để suy luận ngữ cảnh chuẩn xác nhất.

---

### 2. THIẾT KẾ (DESIGN)

* **Kiến trúc hệ thống:**  
  Thuộc Node thứ 2 (`EnrichNode`) trong luồng LangGraph Flow 1 Pipeline (`src/agents/graph.py`). Nhận `raw_schema` từ `IntrospectNode` $\rightarrow$ xử lý batching $\rightarrow$ gọi OpenAI LLM $\rightarrow$ trả về `enriched_schema` lưu vào `AgentState`.
  ```mermaid
  graph LR
      IntrospectNode -->|raw_schema| EnrichNode
      EnrichNode -->|Batching 5 tables| LLM[OpenAI GPT-4o / get_llm]
      LLM -->|JSON Response| Parser[Clean JSON & Validate]
      Parser -->|enriched_schema| MetricSuggestNode
  ```
* **Thiết kế giao diện (UI/UX):**  
  Nằm trên **Màn 2 (HITL Schema Reviewer)** của Web App. Hiển thị bảng so sánh side-by-side giữa `Tên kỹ thuật thô` và `Tên nghiệp vụ tiếng Việt (AI đề xuất)`. Hỗ trợ gõ sửa trực tiếp inline edit trước khi Approve.
* **Thiết kế API:**  
  - Tích hợp trong Pipeline `POST /api/v1/semantic/generate`.
  - API Cập nhật inline khi BA/DA chỉnh sửa: `PUT /api/v1/semantic/{db_id}/column/{table_name}/{column_name}`
    ```json
    // Request Body (SemanticColumnUpdate)
    {
      "business_name": "Tổng Tiền Bao Gồm Thuế VAT",
      "description": "Giá trị thanh toán cuối cùng đã tính 10% thuế VAT."
    }
    ```
* **Mô hình dữ liệu:**  
  Cập nhật bảng `semantic_tables` và `semantic_columns` trong PostgreSQL Metadata Store:
  - `semantic_tables`: `id`, `db_id`, `table_name`, `business_name`, `description`.
  - `semantic_columns`: `id`, `table_id`, `column_name`, `data_type`, `business_name`, `description`, `is_primary_key`.
* **Thiết kế AI/ML:**  
  - **Model:** `ChatOpenAI` thông qua Factory method `get_llm()` từ `src/services/llm.py`.
  - **Hyperparameters:** `temperature=0.0` (Đảm bảo tính nhất quán cao nhất).
  - **Prompt Engineering:** Ép kiểu System Prompt bắt buộc trả về Strict JSON, loại bỏ markdown fence ` ```json `. Đưa từ điển từ viết tắt (`amt`, `qty`, `usr`, `ord`) vào Few-shot context.
* **Trường hợp đặc biệt và Xử lý lỗi:**  
  - *Lỗi Rate Limit / Timeout từ LLM:* Áp dụng cơ chế Fallback tự động `_fallback_enrichment()` biến `amt_vat_inc` thành "Amt Vat Inc" để pipeline tiếp tục chạy mà không crash server.
  - *Lỗi Schema quá lớn (> 50 bảng):* Áp dụng hàm `chunk_tables(batch_size=5)` chia nhỏ để gọi LLM song song (`asyncio.gather`).
* **Bảo mật và Quyền riêng tư:**  
  - `OPENAI_API_KEY` được đọc từ biến môi trường `.env`, tuyệt đối không commit hay log ra console.  
  - Chỉ gửi tên bảng và tên cột sang LLM — **tuyệt đối không gửi dữ liệu thực (data records)**.

---

### 3. KẾ HOẠCH (PLAN)

* **Các bước thực hiện:**  
  1. Xây dựng Prompt template & Few-shot examples tiếng Việt (2h).  
  2. Implement hàm `enrich_node()` async trong `src/agents/nodes/enrich_node.py` (4h).  
  3. Viết hàm `_fallback_enrichment()` và logic batching (2h).  
  4. Viết Unit Test mock LLM response trong `tests/test_agents/test_enrich_node.py` (3h).  
  5. Tích hợp API Update & Giao diện Inline Edit trên UI (4h).
* **Công việc con (liên kết Backlog):**  
  - `[T-101]`: Viết Prompt & JSON parser cho Enrich Node.  
  - `[T-102]`: Implement logic `enrich_node.py` async.  
  - `[T-103]`: Viết Unit Test mock LLM cho Enrich Node.  
  - `[T-104]`: Kết nối API `PUT /column` với Màn hình UI Reviewer.
* **Phụ thuộc:**  
  Phụ thuộc vào `raw_schema` từ `IntrospectNode` (Dev A làm trọn gói nên chủ động 100%).
* **Timeline dự kiến:**  
  04/08/2026 $\rightarrow$ 05/08/2026 (Tổng dự kiến: **15 giờ làm việc**).
* **Kế hoạch kiểm thử:**  
  - *Automated Test:* `pytest tests/test_agents/test_enrich_node.py` pass 100%.  
  - *Manual Test:* Thử nghiệm với file SQL Dump của SQLite e-commerce DB xem tên tiếng Việt sinh ra có tự nhiên và chính xác không.
* **Kế hoạch triển khai:**  
  Release trực tiếp vào nhánh `main` theo quy trình CI/CD Docker Compose.
* **Tiêu chí thành công:**  
  - 100% cột trong schema có `business_name` không bị rỗng.  
  - 100% kết quả là tiếng Việt.  
  - Đạt thời gian xử lý $< 15$s cho 20 bảng.
* **Rủi ro và Cách giảm thiểu:**  
  - *Rủi ro:* LLM trả về JSON bị lỗi cú pháp làm ngắt luồng.  
  - *Giảm thiểu:* Bọc `json.loads` trong khối `try/except` và gọi hàm Fallback nếu có lỗi.

---
---

## ĐẶC TẢ #2

| Trường thông tin | Giá trị |
|---|---|
| **Mã User Story liên quan** | `[US-002]` / `[F-03 & F-10]` |
| **Tên tính năng** | **Business Metric Suggestion & Dedupe Conflict Engine (Đề xuất Chỉ số & Cảnh báo Mâu thuẫn)** |
| **Người viết** | Đội ngũ Phát triển P-069 (Dev C & Lead) |
| **Ngày tạo** | 03/08/2026 |
| **Ngày cập nhật gần nhất** | 03/08/2026 |
| **Trạng thái** | **Đã duyệt** |

---

### 1. ĐỘNG LỰC (MOTIVATION)

* **Vấn đề cần giải quyết:**  
  Doanh nghiệp thiếu một kho quản lý chỉ số (Metrics Library) thống nhất. Mỗi phòng ban (Kế toán vs Sale) tự định nghĩa công thức tính "Doanh Thu" khác nhau (trước thuế vs sau thuế), dẫn đến sai lệch số liệu báo cáo.
* **Người dùng mục tiêu:**  
  Data Lead, Lead BA, Chief Analytics Officer (CAO). Họ cần phát hiện và gộp các công thức tính trùng lặp/mâu thuẫn trước khi công bố metric chính thức.
* **Mục tiêu kỳ vọng:**  
  - AI tự động phân tích cấu trúc bảng/cột để gợi ý 3-5 chỉ số kinh doanh cốt lõi kèm SQL template tham chiếu.  
  - Tự động phát hiện và cắm cờ cảnh báo (Warning Badge) nếu chỉ số gợi ý bị mâu thuẫn/trùng lặp với chỉ số đã lưu trong hệ thống.
* **Phương án thay thế đã xem xét:**  
  - *Phương án 1 (Bắt người dùng nhập thủ công 100%):* BA/DA không biết bắt đầu từ đâu nếu schema quá lớn.  
  - *Chọn phương án:* **LLM Auto-Suggest kết hợp Dedupe Conflict Node & HITL Approval**.

---

### 2. THIẾT KẾ (DESIGN)

* **Kiến trúc hệ thống:**  
  Gồm 2 Node nối tiếp trong LangGraph Pipeline: `MetricSuggestNode` $\rightarrow$ `DedupeNode`.
  ```mermaid
  graph LR
      EnrichNode -->|enriched_schema| MetricSuggestNode
      MetricSuggestNode -->|suggested_metrics| DedupeNode
      DedupeNode -->|Compare with Metadata Store| DedupeNode
      DedupeNode -->|metrics + conflict_flags| HITL[HITL Reviewer UI]
  ```
* **Thiết kế giao diện (UI/UX):**  
  **Màn 3 (Business Metric Library & Conflict Resolution UI)**: Hiển thị danh sách thẻ Metric. Thẻ nào bị trùng/mâu thuẫn sẽ hiển thị Badge đỏ `[⚠️ Mâu thuẫn định nghĩa]` kèm nút so sánh 2 công thức SQL side-by-side để BA/DA bấm nút "Gộp (Merge)", "Ghi đè (Overwrite)" hoặc "Giữ cả hai".
* **Thiết kế API:**  
  - `POST /api/v1/semantic/{db_id}/metric`: Thêm mới metric thủ công.  
  - `PUT /api/v1/semantic/{db_id}/metric/{metric_id}`: Cập nhật công thức/tên metric.  
  - `DELETE /api/v1/semantic/{db_id}/metric/{metric_id}`: Xóa metric bị từ chối.
* **Mô hình dữ liệu:**  
  Tương tác với bảng `semantic_metrics` trong Database:
  - `semantic_metrics`: `id`, `db_id`, `name`, `description`, `sql_template`, `status` (`draft` / `approved` / `conflict`), `created_at`.
* **Thiết kế AI/ML:**  
  - **MetricSuggest Prompt:** Đưa `enriched_schema` vào để LLM tìm các cột dạng `amount`, `quantity`, `price`, `status` và sinh các hàm gom nhóm `SUM`, `COUNT`, `AVG`.  
  - **Dedupe Logic:** LLM so sánh ý nghĩa ngữ nghĩa (Semantic Similarity) giữa Metric vừa gợi ý và các Metric đang có trong `semantic_metrics` DB.
* **Trường hợp đặc biệt và Xử lý lỗi:**  
  Nếu schema không có cột định lượng (numeric/amount/quantity), `MetricSuggestNode` sẽ trả về danh sách rỗng và ghi log `No numeric columns found for metric calculation` mà không gây lỗi app.
* **Bảo mật và Quyền riêng tư:**  
  Chỉ Data Lead / BA có quyền bấm Approve hoặc Delete Metric khỏi thư viện.

---

### 3. KẾ HOẠCH (PLAN)

* **Các bước thực hiện:**  
  1. Viết prompt sinh Metric + SQL Template trong `src/agents/nodes/metric_suggest_node.py` (4h).  
  2. Implement `DedupeNode` so sánh trùng lặp với DB Metadata Store (4h).  
  3. Viết các API CRUD cho Business Metrics trong `src/api/routes.py` (4h).  
  4. Dựng giao diện Màn 3 UI hiển thị Metric Library & Conflict Badge (5h).
* **Công việc con (liên kết Backlog):**  
  - `[T-301]`: Implement `MetricSuggestNode` & Prompt engineering.  
  - `[T-302]`: Implement `DedupeNode` & Conflict checking logic.  
  - `[T-303]`: Xây dựng CRUD APIs cho Business Metrics.  
  - `[T-304]`: Dựng Màn 3 UI Quản lý Metric & Conflict Resolution.
* **Phụ thuộc:**  
  Cần `enriched_schema` từ `EnrichNode` làm input.
* **Timeline dự kiến:**  
  06/08/2026 $\rightarrow$ 07/08/2026 (Tổng dự kiến: **17 giờ làm việc**).
* **Kế hoạch kiểm thử:**  
  - *Unit Test:* Test `DedupeNode` với 2 metric trùng tên nhưng khác câu lệnh SQL `SUM(total)` vs `SUM(subtotal + vat)`.  
  - *UI Test:* Kiểm tra thao tác sửa công thức SQL trực tiếp trên UI và bấm "Approve".
* **Kế hoạch triển khai:**  
  Đóng gói chung trong Docker Image Backend & Frontend.
* **Tiêu chí thành công:**  
  - AI gợi ý được ít nhất 2-3 chỉ số có câu lệnh SQL hợp lệ syntactically.  
  - Cảnh báo đúng 100% các chỉ số bị trùng tên hoặc trùng công thức.
* **Rủi ro và Cách giảm thiểu:**  
  - *Rủi ro:* Câu lệnh SQL do LLM gợi ý bị sai tên cột kỹ thuật.  
  - *Giảm thiểu:* LLM chỉ được dùng đúng danh sách tên cột có trong `enriched_schema` được cung cấp trong prompt.
