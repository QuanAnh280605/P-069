# 📋 Kế hoạch Hành động (Action Plan) — Căn chỉnh  AI Semantic Layer

> **⚠️ Lưu ý:** Đây là tài liệu phân tích nội bộ, đề xuất mở rộng scope trong tương lai.
> **Scope chính thức của v1.0** được xác định bởi `AGENTS.md`, `PRD.md` và `ARCHITECTURE.md`.
> Các tính năng NL2SQL (Flow 2), Vector DB, DedupeNode **không thuộc v1.0 MVP**.

Tài liệu này đối chiếu **hiện trạng tài liệu dự án** (như PRD, ARCHITECTURE, AGENTS.md) với **yêu cầu gốc của đề bài**. 
Hiện trạng dự án đang được giới hạn (scope down), dẫn đến việc cắt bỏ hoàn toàn những tính năng đắt giá nhất mà đề bài yêu cầu. Tài liệu này chỉ ra 3 lỗ hổng logic lớn nhất và đề xuất các đầu việc cần làm để khắc phục.

---

## 1. Phân Tích 3 Mâu Thuẫn Logic Lớn Nhất Cần Khắc Phục

### 1.1. Tính năng "Hỏi chỉ số bằng Ngôn ngữ tự nhiên (NL2SQL)"
* **Yêu cầu đề bài:** Dự án phải *"cho phép hỏi chỉ số bằng NL và tự dịch sang query dựa trên metric đã chuẩn hóa"* và luồng agent có bước *"NL-to-metric query"*.
* **Tài liệu hiện tại:** Đang có quy tắc cấm: *"Không phải NL2SQL chatbot. Không implement Flow 2 trong v1.0."*
* **Bản chất vấn đề:** Toàn bộ mục đích của việc xây dựng "Semantic Layer" (Lớp Ngữ Nghĩa) là để AI có thể hiểu câu hỏi của con người. Nếu bạn chỉ dùng AI để đặt tên tiếng Việt (Flow 1) rồi lưu vào DB mà không xây dựng Flow 2 (Hỏi/Đáp) thì  của bạn chỉ là một "Tool tạo Data Dictionary" chứ chưa phải là một **Semantic Layer Agent** hoàn chỉnh.
* **Hành động (Những việc phải làm):** 
  - [ ] **Sửa PRD.md:** Chuyển tính năng "Natural Language Query (NL2SQL)" từ phần Out-of-Scope sang In-Scope (ưu tiên P1).
  - [ ] **Sửa ARCHITECTURE.md:** Bổ sung thêm Sơ đồ luồng xử lý (Flow 2) cho việc nhận câu hỏi Text của user, tìm kiếm ngữ nghĩa, và sinh ra câu query SQL.
  - [ ] **Thiết kế API:** Cần thêm endpoint `POST /api/v1/semantic/query` để phục vụ riêng cho Frontend Chatbot.

### 1.2. Sự cần thiết của Cơ sở dữ liệu Vector (Vector DB)
* **Yêu cầu đề bài:** Chỉ định rõ công nghệ: *"vector DB lưu định nghĩa"*.
* **Tài liệu hiện tại:** Không dùng ChromaDB, FAISS hay vector store nào.
* **Bản chất vấn đề:** Khi User hỏi *"Số tiền thu được tháng này là bao nhiêu?"*, AI phải đối chiếu câu hỏi này với định nghĩa có tên là *"Doanh Thu"*. Cơ sở dữ liệu thông thường (PostgreSQL) sử dụng tìm kiếm từ khóa chính xác (Exact Match) sẽ không hiểu *"Số tiền thu được"* nghĩa là *"Doanh Thu"*. Chỉ có Vector DB mới có thể tìm kiếm theo ngữ nghĩa (Semantic Search) để xử lý việc này. 
* **Hành động (Những việc phải làm):**
  - [ ] **Xóa quy tắc cấm:** Gỡ bỏ dòng cấm sử dụng Vector DB trong `AGENTS.md`.
  - [ ] **Chốt công nghệ:** Quyết định sẽ dùng Vector DB riêng (như ChromaDB) hay dùng extension `pgvector` (đề xuất dùng `pgvector` để tận dụng luôn PostgreSQL hiện có). Cập nhật quyết định này vào `ARCHITECTURE.md`.
  - [ ] **Thiết kế luồng Embedding:** Bổ sung logic: Bất cứ khi nào một Metric được duyệt (HITL Approve), hệ thống tự động băm (Embed) tên/mô tả của Metric đó và lưu vào Vector DB.

### 1.3. Logic của Node "Khử trùng lặp & Mâu thuẫn" (Dedupe)
* **Yêu cầu đề bài:** Luồng Agent phải là: `extract metric` ➔ `dedupe` ➔ `define` ➔ `NL query`. Đề bài nhấn mạnh việc *"phát hiện định nghĩa trùng/mâu thuẫn"*.
* **Tài liệu hiện tại:** Luồng Agent hiện tại là: `Introspect` ➔ `Enrich` ➔ `Metric Suggest` ➔ `Save`. Bỏ qua hoàn toàn bước `Dedupe`.
* **Bản chất vấn đề:** Thực tế doanh nghiệp luôn có sự mâu thuẫn (VD: Phòng Sale tính doanh thu trước thuế, Phòng Kế toán tính sau thuế). Khi Agent trích xuất schema, nó có thể gợi ý ra 2 chỉ số đều tên là "Doanh Thu" nhưng có công thức SQL khác nhau. Nếu không có Node `Dedupe`, hệ thống sẽ lưu cả 2 vào DB →  thất bại vì không giải quyết được "pain point" của bài toán.
* **Hành động (Những việc phải làm):**
  - [ ] **Cập nhật Sơ đồ kiến trúc:** Vẽ lại sơ đồ Mermaid trong `ARCHITECTURE.md`, chèn thêm một Node `Dedupe` đứng giữa Node `Suggest` và Node `HITL`.
  - [ ] **Định nghĩa Logic xử lý:** Cập nhật vào `PRD.md` cách hệ thống phát hiện trùng lặp (ví dụ: LLM so sánh độ tương đồng 2 công thức SQL, hoặc dùng thuật toán text similarity).
  - [ ] **Cập nhật giao diện HITL:** Yêu cầu UI phải có phần hiển thị "Cảnh báo mâu thuẫn" để Data Lead vào giải quyết: Gộp (Merge), Xóa, hoặc giữ cả 2 chỉ số.

---

## 2. Các Đầu Việc Tổng Quát Cần Bổ Sung (Roadmap)

Dựa trên phân tích trên, dưới đây là các Epic/Task lớn cần thực hiện để  bám sát yêu cầu:

### EPIC 1: Nâng cấp Kiến trúc & PRD (Thiết kế lại Scope)
- **Task 1.1:** Cập nhật file `PRD.md` và `ARCHITECTURE.md` để đưa tính năng **"NL-to-metric query" (Flow 2)** vào phạm vi .
- **Task 1.2:** Thiết kế lại sơ đồ LangGraph để bổ sung Node **Dedupe** (Phát hiện và cảnh báo định nghĩa trùng/mâu thuẫn trước khi duyệt).
- **Task 1.3:** Cập nhật sơ đồ kiến trúc để đưa **Vector DB** vào làm nơi lưu trữ Embedding của các Metric đã được duyệt.

### EPIC 2: Phát triển Backend AI Agent (Core Logic)
- **Task 2.1:** Hoàn thiện luồng **Define** (Tự động trích xuất cấu trúc DB, dùng LLM dịch tên kỹ thuật sang nghiệp vụ - phần này đã có bộ khung, cần code chi tiết).
- **Task 2.2:** Xây dựng logic cho **Dedupe Node**: So sánh Metric LLM vừa gợi ý với các Metric đang có trong hệ thống.
- **Task 2.3:** Phát triển luồng **NL-to-Metric (Chatbot)**: Nhận câu hỏi từ User, dùng LLM tạo Vector Search để tìm Metric chuẩn đã định nghĩa, sau đó tự sinh câu query.

### EPIC 3: Bổ sung tính năng Nâng cao (Theo đề bài)
- **Task 3.1:** Tính năng **Versioning & Phân quyền (RBAC)**: Quản lý 2 vai trò (Data Lead duyệt/ban hành, Analyst đề xuất). Mỗi khi sửa Metric phải tạo version mới (Governance).
- **Task 3.2 (Advanced):** Xây dựng hệ thống **Multi-agent**: Tạo các Agent đóng vai trò các phòng ban khác nhau tranh biện và hòa giải để thống nhất 1 công thức metric chung.
- **Task 3.3 (Advanced):** Hệ thống **Evaluation**: Đo độ khớp của số liệu (truy vấn qua semantic layer vs truy vấn thủ công bằng SQL thường).

### EPIC 4: Tích hợp Hệ sinh thái Dữ liệu
- **Task 4.1:** Mở rộng kết nối Target DB để hỗ trợ **BigQuery** và **Snowflake** (Các Data Warehouse tiêu chuẩn ngành).
- **Task 4.2:** Viết module `ExportService` có khả năng xuất định nghĩa Metric ra đúng format của **dbt Semantic Layer** (`.yml`) hoặc **Cube.dev** (`.js`).

### EPIC 5: Giao diện (Frontend) & Triển khai (Deployment)
- **Task 5.1:** Khởi tạo project **Next.js** cho Frontend. Xây dựng UI 2 phần: (1) Màn hình HITL cho Data Lead duyệt Metric, (2) Khung chat cho phép hỏi chỉ số bằng NL.
- **Task 5.2:** Đóng gói toàn bộ Backend API và Frontend thành Docker images.
- **Task 5.3:** Thiết lập **GitHub Actions** CI/CD để tự động deploy lên **Google Cloud Run** theo đúng yêu cầu công nghệ.

---

## 3. Kết luận về Logic Phát triển
Việc các tài liệu hiện tại (như PRD/ARCHITECTURE/AGENTS.md) đang cố tình cấm dùng Vector DB hoặc loại bỏ luồng "Hỏi bằng ngôn ngữ tự nhiên" là **đi ngược lại với yêu cầu **. 

Để bắt đầu đúng hướng, toàn bộ bước thiết kế Logic của bạn bây giờ phải là: **Xóa bỏ các giới hạn sai lầm đó, bổ sung lại Vector DB, Next.js và Dedupe logic vào bộ tài liệu phân tích hệ thống (`PRD.md`, `ARCHITECTURE.md`) trước khi bắt đầu code.**
