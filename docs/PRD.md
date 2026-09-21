# 📑 Product Requirements Document (PRD) — AI Semantic Layer Agent

> **Tên sản phẩm:** AI Semantic Layer Agent  
> **Phiên bản:** v1.0.0 (Build Phase Capstone)  
> **Trạng thái:** Hoàn thiện & Khớp mã nguồn thực tế  
> **Tác giả:** Đội ngũ Phát triển P-069  

---

## 1. Mục tiêu Sản phẩm (Product Goals)

1. **Chuẩn hóa Semantic Layer Doanh nghiệp (Unified Semantic Layer):** Tự động chuyển đổi cấu trúc kỹ thuật phức tạp của cơ sở dữ liệu (`usr_tbl_01`, `amt_vat_inc`) thành lớp ngữ nghĩa kinh doanh rõ ràng bằng tiếng Việt thông qua mô hình AI 2-Pass Clustering, đảm bảo tính đồng nhất thuật ngữ trên toàn bộ tổ chức.
2. **Quản trị Chỉ số Kinh doanh Tập trung & Lịch sử Phiên bản (Metric Governance & Versioning):** Cung cấp một "nguồn sự thật duy nhất" (Single Source of Truth) cho các công thức tính chỉ số kinh doanh, hỗ trợ phân loại nguồn (`ai` vs `manual`), trạng thái phê duyệt (Approval) và lưu vết toàn bộ lịch sử thay đổi công thức (`metric_versions`).
3. **Biên dịch Truy vấn Dữ liệu Chuẩn xác & An toàn (Deterministic Safe Query Engine):** Cho phép người dùng trực quan lựa chọn Metrics và Dimensions để biên dịch thành SQL chuẩn xác 100% qua `SemanticQueryCompiler` và thực thi Read-Only có Guardrails (`sqlglot`, `LIMIT 100`, `timeout = 15s`) trên Live Database.
4. **Trợ lý AI Hội thoại & Wizard Làm rõ Truy vấn (Conversational Studio & Clarifier):** Tích hợp tác tử hội thoại thông minh hỗ trợ giải đáp và định nghĩa metric, cùng Wizard hướng dẫn người dùng từng bước làm rõ các yêu cầu truy vấn còn mơ hồ.

---

## 2. Đối tượng Người dùng & Chân dung (User Personas)

RBAC chỉ có phạm vi **Workspace**; không tồn tại vai trò ứng dụng toàn cục trên tài khoản. Một người có thể giữ vai trò khác nhau trong các Workspace khác nhau.

### Persona 1: Workspace Admin
- **Mục tiêu:** Quản trị thành viên, tạo/thu hồi URL mời và gán vai trò trong Workspace.
- **Ranh giới:** Không quản trị schema hoặc metric; không phải Admin toàn nền tảng; **không tạo hay gửi metric** (không có quyền `can_generate_metrics`) nhưng vẫn dùng chat/query thông thường. Workspace luôn phải còn ít nhất một Admin.

### Persona 2 (Chính): Data Lead / Analytics Engineer
- **Mục tiêu:** Quản trị schema/kết nối, thiết lập `canonical_relationships`, tạo và quản lý metric, xét duyệt submission của Member và khai thác Live Database an toàn.
- **Nhu cầu:** Chỉnh sửa/xóa metric chưa duyệt, phê duyệt `unverified -> approved`, truy vết lịch sử, chọn `preferred_join_paths` khi có nhiều đường JOIN, và dùng Query Engine với Guardrails bắt buộc.
- **Ranh giới:** Không quản trị thành viên hoặc invitation. Quyền tạo/gửi metric được kiểm soát bởi `can_generate_metrics` (thay thế khái niệm `can_use_metric_studio` cũ).

### Persona 3: Member / Business Analyst
- **Mục tiêu:** Gửi đề xuất metric mới (trạng thái `unverified`), theo dõi submission của chính mình và sử dụng catalog metric đã duyệt để query/chat.
- **Ranh giới:** Submission được tạo ở trạng thái `unverified` và Member không thể sửa, xóa hay tự phê duyệt sau khi gửi; Member không có quyền `can_generate_metrics` nên không tạo metric trực tiếp.

---

## 3. Danh sách Tính năng & Trạng thái Hiện thực (Feature Matrix)

| Feature ID | Tên tính năng | Mô tả chi tiết | Mức ưu tiên | Trạng thái |
|---|---|---|---|---|
| **F-01** | Database Schema Introspection | Kết nối Target Live DB (Postgres/MySQL/SQLite), đọc metadata qua `SQLAlchemy Inspector`. Chỉ đọc metadata cấu trúc, không đọc dữ liệu. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-02** | SQL Dump Scanner & Parser | Tải lên file `.sql` DDL (PostgreSQL, MySQL, SQLite), quét và phân tích AST trích xuất bảng, cột, khóa ngoại kèm Technical Preview & Diagnostics. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-03** | 2-Pass Clustering AI Enrichment | **Pass 1:** Xây dựng từ điển thuật ngữ miền toàn cục. **Clustering:** Phân cụm đồ thị bảng. **Pass 2:** Sinh tên nghiệp vụ và mô tả tiếng Việt chi tiết kèm Fallback tự động. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-04** | Canonical Relationships Builder | Tự động phân tích và xác định Primary Key, Foreign Key, Time Dimension và cấu trúc quan hệ liên bảng phục vụ giải quyết đường đi JOIN. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-05** | Metric Suggestion & Generation | AI tự động gợi ý Business Metrics từ schema hoặc sinh metric tùy biến dựa trên prompt yêu cầu của người dùng. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-06** | HITL Review & Inline Editing | Giao diện Web cho phép BA/DA xem xét, chỉnh sửa trực tiếp tên nghiệp vụ bảng/cột và duyệt Semantic Layer trước khi lưu chính thức. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-07** | Metric Versioning & Audit Trail | Quản trị vòng đời chỉ số: phân loại nguồn, trạng thái duyệt (Approve), lưu vết toàn bộ lịch sử chỉnh sửa công thức (`metric_versions`). | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-08** | Deterministic Semantic Query Compiler | Biên dịch trực quan các Metrics, Dimensions và Filters thành SQL chuẩn xác 100% theo dialect của Target DB dựa trên quan hệ canonical. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-09** | Live DB Query Execution & Guardrails | Thực thi Read-Only an toàn trên Live DB: Kiểm tra AST `sqlglot` ép duy nhất lệnh SELECT, auto `LIMIT 100` (max 1000) và `timeout = 15s`. | **P0 (Must-Have)** | ✅ Đã hoàn thành |
| **F-10** | Conversational AI Studio | Khung chat trực tuyến điều phối đa tác tử (`chat_graph`) tự động phân loại ý định giữa trò chuyện chung và yêu cầu sinh metric. | **P1 (Should-Have)** | ✅ Đã hoàn thành |
| **F-11** | Multi-turn Query Clarifier Wizard | Wizard hỏi đáp tương tác từng bước (`query_clarifier`) giúp người dùng làm rõ các câu hỏi truy vấn mơ hồ trước khi chuyển sang Explorer. | **P1 (Should-Have)** | ✅ Đã hoàn thành |
| **F-12** | Export Semantic Layer (JSON/YAML) | Đóng gói và xuất Semantic Layer đã duyệt ra định dạng JSON hoặc YAML tương thích với các công cụ BI (dbt, Metabase). | **P1 (Should-Have)** | ✅ Đã hoàn thành |

---

## 4. User Stories & Tiêu chí Chấp nhận (Acceptance Criteria)

### Story 1: Tự động phân tích Schema qua 2-Pass AI Enrichment
- **Là một** Business Analyst,  
- **Tôi muốn** cung cấp Connection URL của Live DB hoặc tải lên file SQL Dump để hệ thống tự động phân tích và enrich schema,  
- **Để** tôi có bản đặc tả tên nghiệp vụ tiếng Việt và mô tả chi tiết mà không phải nhập liệu thủ công.
- **Tiêu chí chấp nhận:**
  - Hệ thống trích xuất đầy đủ danh sách bảng, cột, kiểu dữ liệu, khóa chính và khóa ngoại.
  - LLM thực hiện Pass 1 sinh Domain Glossary và Pass 2 sinh `business_name`, `description` tiếng Việt.
  - Áp dụng cơ chế Fallback nếu LLM gặp lỗi cú pháp hoặc timeout.
  - Trả về cấu trúc Semantic Layer hoàn chỉnh ở trạng thái draft.

### Story 2: Quản trị Chỉ số, Phê duyệt & Lịch sử Phiên bản (Metric Versioning)
- **Là một** Data Lead,  
- **Tôi muốn** phê duyệt các chỉ số AI đề xuất, chỉnh sửa công thức và xem lại toàn bộ lịch sử các lần sửa đổi,  
- **Để** đảm bảo công thức chỉ số luôn chuẩn xác và có thể truy vết nguồn gốc thay đổi.
- **Tiêu chí chấp nhận:**
  - API `POST /api/v1/semantic/{db_id}/metric/{metric_id}/approve` cập nhật trạng thái hoạt động.
  - Khi chỉnh sửa metric qua `PUT`, hệ thống tự động tăng `version` và ghi bản ghi mới vào `metric_versions`.
  - API `GET /api/v1/semantic/{db_id}/metric/{metric_id}/history` trả về đầy đủ danh sách các phiên bản cũ và lý do thay đổi.

### Story 3: Biên dịch & Thực thi Truy vấn An toàn trên Live DB (Flow 2)
- **Là một** Data Analyst,  
- **Tôi muốn** lựa chọn các Metrics và Dimensions trực tiếp từ giao diện để xem trước SQL và thực thi lấy dữ liệu từ Live DB,  
- **Để** có báo cáo dữ liệu chính xác 100% mà không cần viết SQL thủ công.
- **Tiêu chí chấp nhận:**
  - `POST /api/v1/semantic/{db_id}/query/compile` trả về câu lệnh SQL và diagnostics mà không chạm tới Target DB.
  - `POST /api/v1/semantic/{db_id}/query` thực thi câu lệnh Read-Only trên Live DB.
  - Bắt buộc kiểm tra AST với `sqlglot`: Chặn tuyệt đối `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`.
  - Tự động áp dụng `LIMIT 100` và `statement_timeout = 15s`.
  - Nếu nguồn là SQL Dump, trả về mã lỗi HTTP 400 rõ ràng.

### Story 4: Trợ lý Hội thoại & Wizard Làm rõ Truy vấn
- **Là một** Người dùng Nghiệp vụ,  
- **Tôi muốn** trò chuyện với trợ lý AI hoặc sử dụng Wizard để biến câu hỏi kinh doanh mơ hồ thành cấu trúc truy vấn chuẩn,  
- **Để** dễ dàng tiếp cận dữ liệu mà không cần hiểu sâu cấu trúc bảng kỹ thuật.
- **Tiêu chí chấp nhận:**
  - Chat Studio tự động nhận diện câu hỏi chào hỏi (`chitchat`) hoặc câu hỏi chỉ số (`metric_query`).
  - Query Wizard hỏi đáp tương tác từng bước và trả về cấu trúc Metric/Dimension đã chuẩn hóa.

---

## 5. Yêu cầu Phi chức năng (Non-Functional Requirements)

1. **Bảo mật & Mã hóa:**
   - Connection URL của Target DB bắt buộc mã hóa bằng Fernet đối xứng trước khi lưu.
   - Mật khẩu người dùng được băm an toàn bằng Bcrypt (cost factor 12).
   - Xác thực API qua JWT Bearer token và Refresh Token có thể thu hồi.
2. **Tính Ổn định & Độ tin cậy:**
   - LLM sử dụng `temperature = 0.0` để đảm bảo output đồng nhất.
   - Flow 2 biên dịch SQL thuần túy từ template & graph quan hệ, không dùng Text-to-SQL tự do.
3. **Hiệu năng:**
   - Thời gian phân tích và enrich schema $\le 20$ bảng trong vòng $< 30$ giây.
   - Thời gian biên dịch truy vấn Semantic Query trong vòng $< 100$ mili-giây.
