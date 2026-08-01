# 🎨 Wireframe & UI Flow Document — AI Semantic Layer Agent

> **Tài liệu:** Thiết kế Luồng màn hình (UI Flow) & Bố cục Sơ bộ (Wireframes)  
> **Dự án:** AI Semantic Layer Agent  
> **Mục đích:** Định hình trải nghiệm người dùng, thống nhất layout các màn hình trước và trong quá trình phát triển Frontend.

---

## 1. Luồng di chuyển giữa các màn hình (User Navigation Flow)

Diagram dưới đây mô tả cách người dùng di chuyển qua các màn hình chính của ứng dụng:

```mermaid
flowchart TD
    S1["🖥️ Màn hình 1\nQuản lý Kết nối Database"]
    S2["⚙️ Màn hình 2\nSemantic Layer Builder & HITL Review"]
    S2note["✏️ Tab A: Bảng & Cột\n✏️ Tab B: Business Metrics Library"]
    S3["📤 Màn hình 3\nExport & Chia sẻ Semantic Layer"]
    M1["🔌 Modal: Kết nối DB mới"]
    M2["➕ Modal: Thêm Metric thủ công"]

    S1 -->|"① Kết nối DB mới"| M1
    M1 -->|"Introspect thành công"| S2
    S1 -->|"Mở layer có sẵn"| S2
    S2 --- S2note
    S2note -->|"Tab B: Thêm Metric thủ công"| M2
    M2 -->|"Xác nhận"| S2
    S2 -->|"② Chốt & Lưu Semantic Layer"| S1
    S2 -->|"③ Export"| S3
    S3 -->|"Quay lại"| S2
```

---

## 2. Bố cục Sơ bộ từng Màn hình (Wireframes & Screen Layouts)

---

### 🖥️ Màn hình 1: Quản lý Kết nối Database (`/`)

**Mục đích:** Trang chủ — người dùng kết nối với Target Database mới hoặc mở một Semantic Layer đã có trong hệ thống để tiếp tục chỉnh sửa.

```
+-----------------------------------------------------------------------------------+
| 🤖 AI SEMANTIC LAYER AGENT                      [ Docs ]  [ Settings ]  [ Admin ] |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  ➕ KẾT NỐI DATABASE MỚI                                                           |
|  -------------------------------------------------------------------------------  |
|  Tên gợi nhớ DB: [ e.g. E-Commerce Production Database                      ]    |
|  Loại DB:        (*) PostgreSQL   ( ) MySQL   ( ) SQLite                          |
|  Connection URL: [ postgresql://user:pass@localhost:5432/ecommerce_db       ]    |
|                                                                                   |
|                  [ ⚡ Bắt đầu Phân tích Schema (Auto Introspect & Enrich) ]       |
|                                                                                   |
| ================================================================================= |
|                                                                                   |
|  📁 DANH SÁCH SEMANTIC LAYERS ĐÃ TẠO                                              |
|  -------------------------------------------------------------------------------  |
|  +---------------------------+---------------------+-------------------+--------+ |
|  | Tên Database              | Loại DB             | Ngày cập nhật     | Thao tác| |
|  +---------------------------+---------------------+-------------------+--------+ |
|  | E-Commerce Prod DB        | PostgreSQL          | 2026-07-31 10:00  | [ Mở ] | |
|  | Retail Sales SQLite       | SQLite              | 2026-07-30 14:20  | [ Mở ] | |
|  +---------------------------+---------------------+-------------------+--------+ |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

**Trạng thái Loading (khi đang Introspect):**
```
+-----------------------------------------------------------------------------------+
| ⚙️ ĐANG PHÂN TÍCH SCHEMA...                                                        |
|  ● Introspecting schema...         ✅ Xong (2.1s)                                 |
|  ● Enriching table & column names... ⏳ Đang xử lý...                             |
|  ● Suggesting business metrics...  ⏸ Chờ bước trên                               |
+-----------------------------------------------------------------------------------+
```

---

### ⚙️ Màn hình 2: Semantic Layer Builder & HITL Review (`/semantic/{db_id}/review`)

**Mục đích:** Hiển thị kết quả AI đã tự động phân tích (Introspect + Enrich + Metric Suggest). Cho phép BA/DA chỉnh sửa trực tiếp tên nghiệp vụ, mô tả cột và duyệt/thêm/sửa/xóa Business Metrics trước khi lưu chính thức.

```
+-----------------------------------------------------------------------------------+
| ← Quay lại   |  ⚙️ REVIEW SEMANTIC LAYER: E-Commerce Prod DB    [ 📤 Export ] [ 💾 Lưu Chính Thức ] |
+-----------------------------------------------------------------------------------+
| [ TAB A: BẢNG & CỘT (TABLES & COLUMNS) ]    [ TAB B: BUSINESS METRICS LIBRARY (3) ] |
+-----------------------------------------------------------------------------------+
|                                                                                   |
| 📂 Bảng: orders                                                                    |
|    Tên nghiệp vụ: [ Đơn hàng                                      ] ✏️            |
|    Mô tả:         [ Bảng chứa thông tin lịch sử mua hàng của KH   ] ✏️            |
|                                                                                   |
|   +-------------------+-----------------------+-----------------------+---------+ |
|   | Tên Cột DB        | Kiểu Dữ Liệu          | Tên Nghiệp Vụ (AI)    | Mẫu DL  | |
|   +-------------------+-----------------------+-----------------------+---------+ |
|   | order_id          | INTEGER (PK)          | [ Mã đơn hàng       ] | 1001    | |
|   | customer_id       | INTEGER (FK→customers)| [ Mã khách hàng     ] | C-88    | |
|   | total_amount      | NUMERIC               | [ Tổng tiền đơn hàng] | 450,000 | |
|   | order_status      | VARCHAR(20)           | [ Trạng thái đơn    ] | COMPLETED|
|   | created_at        | TIMESTAMP             | [ Ngày tạo đơn      ] | 2026-07 | |
|   +-------------------+-----------------------+-----------------------+---------+ |
|                                                                                   |
| --------------------------------------------------------------------------------- |
| 📂 Bảng: customers  (Tên nghiệp vụ: [ Khách hàng ] ✏️)                            |
| ...                                                                               |
+-----------------------------------------------------------------------------------+
```

**Tab B — Business Metrics Library:**
```
+-----------------------------------------------------------------------------------+
| [ TAB A: BẢNG & CỘT ]    [ TAB B: BUSINESS METRICS LIBRARY (3) ]                  |
+-----------------------------------------------------------------------------------+
|                                         [ ➕ Thêm Metric thủ công ]               |
|                                                                                   |
| ┌─────────────────────────────────────────────────────────────────────────────┐   |
| │ [AI] 1. Doanh thu theo ngày                                                 │   |
| │      Mô tả: Tổng doanh thu phân nhóm theo ngày tạo đơn hàng                │   |
| │      SQL Template:                                                          │   |
| │        SELECT DATE(created_at), SUM(total_amount) FROM orders               │   |
| │        WHERE order_status = 'COMPLETED' GROUP BY 1 ORDER BY 1               │   |
| │                                      [ ✏️ Sửa ]   [ ❌ Xóa ]               │   |
| └─────────────────────────────────────────────────────────────────────────────┘   |
|                                                                                   |
| ┌─────────────────────────────────────────────────────────────────────────────┐   |
| │ [AI] 2. Số lượng đơn hàng theo trạng thái                                  │   |
| │      Mô tả: Đếm số đơn phân nhóm theo trạng thái xử lý                    │   |
| │      SQL Template:                                                          │   |
| │        SELECT order_status, COUNT(*) FROM orders GROUP BY order_status      │   |
| │                                      [ ✏️ Sửa ]   [ ❌ Xóa ]               │   |
| └─────────────────────────────────────────────────────────────────────────────┘   |
|                                                                                   |
| ┌─────────────────────────────────────────────────────────────────────────────┐   |
| │ [Manual] 3. Tỷ lệ đơn hàng hoàn thành (Completion Rate)                   │   |
| │      Mô tả: % đơn hàng có status COMPLETED / tổng đơn hàng                 │   |
| │      SQL Template:                                                          │   |
| │        SELECT ROUND(                                                        │   |
| │          COUNT(*) FILTER(WHERE order_status='COMPLETED') * 100.0            │   |
| │          / COUNT(*), 2) AS completion_rate FROM orders                      │   |
| │                                      [ ✏️ Sửa ]   [ ❌ Xóa ]               │   |
| └─────────────────────────────────────────────────────────────────────────────┘   |
+-----------------------------------------------------------------------------------+
```

---

### 💾 Modal: Thêm / Sửa Business Metric thủ công

**Mục đích:** Xuất hiện khi BA/DA nhấp "Thêm Metric thủ công" hoặc "Sửa" một metric đã có. Cho phép định nghĩa chỉ số không phụ thuộc vào AI.

```
+-----------------------------------------------------------------------------------+
| ➕ THÊM BUSINESS METRIC                                                        [X] |
+-----------------------------------------------------------------------------------+
|                                                                                   |
| Tên Metric:       [ Tỷ lệ đơn hàng hoàn thành (Completion Rate)              ]   |
|                                                                                   |
| Mô tả nghiệp vụ:  [ % đơn hàng có status COMPLETED trên tổng số đơn hàng    ]   |
|                                                                                   |
| SQL Template (tham chiếu):                                                        |
| +-------------------------------------------------------------------------------+ |
| | SELECT ROUND(                                                                 | |
| |   COUNT(*) FILTER(WHERE order_status = 'COMPLETED') * 100.0                  | |
| |   / COUNT(*), 2) AS completion_rate                                           | |
| | FROM orders                                                                   | |
| +-------------------------------------------------------------------------------+ |
|                                                                                   |
|                                [ Hủy bỏ ]   [ 💾 Lưu Metric ]                    |
+-----------------------------------------------------------------------------------+
```

---

### 📤 Màn hình 3: Export & Chia sẻ Semantic Layer (`/semantic/{db_id}/export`)

**Mục đích:** Cho phép BA/DA xuất Semantic Layer đã duyệt ra file để tích hợp với các công cụ BI hoặc chia sẻ với team khác.

```
+-----------------------------------------------------------------------------------+
| ← Quay lại Review   |  📤 EXPORT SEMANTIC LAYER: E-Commerce Prod DB               |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  CHỌN ĐỊNH DẠNG XUẤT:                                                             |
|                                                                                   |
|  ┌────────────────────────────┐   ┌────────────────────────────┐                  |
|  │  📄 JSON                   │   │  📋 YAML                   │                  |
|  │  Tương thích: REST API,    │   │  Tương thích: dbt, Looker  │                  |
|  │  Metabase, custom tools    │   │  Studio, Metabase          │                  |
|  │                            │   │                            │                  |
|  │  [ ⬇️ Tải về JSON ]         │   │  [ ⬇️ Tải về YAML ]         │                  |
|  └────────────────────────────┘   └────────────────────────────┘                  |
|                                                                                   |
|  PREVIEW (JSON):                                                                  |
|  +-------------------------------------------------------------------------------+ |
|  | {                                                                             | |
|  |   "db_name": "E-Commerce Prod DB",                                            | |
|  |   "db_type": "postgresql",                                                    | |
|  |   "generated_at": "2026-07-31T10:00:00Z",                                    | |
|  |   "tables": [                                                                 | |
|  |     {                                                                         | |
|  |       "table_name": "orders",                                                 | |
|  |       "business_name": "Đơn hàng",                                           | |
|  |       "description": "Bảng chứa thông tin lịch sử mua hàng của KH",          | |
|  |       "columns": [...]                                                        | |
|  |     }                                                                         | |
|  |   ],                                                                          | |
|  |   "metrics": [...]                                                            | |
|  | }                                                                             | |
|  +-------------------------------------------------------------------------------+ |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Quy tắc Thiết kế & Trải nghiệm Người dùng (UX Rules)

1. **Hiển thị tiến trình rõ ràng (Progress Feedback):** Trong lúc AI phân tích Schema (Introspect → Enrich → Metric Suggest), luôn hiển thị Step Indicator với trạng thái từng bước: `✅ Xong`, `⏳ Đang xử lý`, `⏸ Chờ`.
2. **Phân biệt nguồn gốc Metric:** Metric do AI đề xuất gắn nhãn `[AI]`, metric do BA/DA thêm thủ công gắn nhãn `[Manual]` để dễ phân biệt mức độ tin cậy.
3. **Thao tác 1-Click HITL:** Mọi định nghĩa AI đề xuất đều có thể sửa nhanh với icon cây bút ✏️ hoặc xóa ❌ ngay tại chỗ, không cần mở trang riêng.
4. **Trạng thái Lưu rõ ràng:** Phân biệt rõ `Draft` (chưa lưu) và `Saved` (đã lưu chính thức) qua badge màu ở header màn hình 2.
