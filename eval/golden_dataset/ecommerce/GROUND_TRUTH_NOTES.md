# GROUND_TRUTH_NOTES — Ecommerce Golden Dataset v3.0.0

Ghi chú quyết định ground truth cho domain `ecommerce`. Mọi khác biệt so với
workbook nguồn (`D:\T069-S206\Ecommerce_Metric_Dictionary_Ground_Truth_Expanded.xlsx`,
19 metric, row 7–25; metric 20 `product_like_rate` đã bị xóa khỏi workbook nên bỏ qua)
được liệt kê ở đây kèm lý do. Audit tham chiếu: `my_docs/AUDIT_Ecommerce_Metric_Dictionary_Expanded.md`.

## 1. Chính sách "đơn hợp lệ" (valid-order policy)

Áp dụng thống nhất cho mọi metric phía đơn hàng:

- **Đơn hợp lệ** = `is_test_order = FALSE AND is_canceled = FALSE`.
- Metric doanh thu / số đơn (net_revenue, order_count, average_order_value,
  gross_margin, returned_order_rate, units_per_transaction) **chỉ tính trên đơn hợp lệ**.
- Metric đo "hành vi đặt hàng" nói chung (discount_rate, order_cancellation_rate,
  loyalty_order_penetration, customer_count, returning_customer_rate, units_sold)
  chỉ cần `is_test_order = FALSE` — mẫu số/ví dụ tính trên toàn bộ đơn thật phát sinh,
  **bao gồm cả đơn bị hủy**, vì bản chất các metric này đo tỷ lệ trên tổng phát sinh.
- Lý do: workbook mâu thuẫn nội tại giữa mô tả net_revenue (loại đơn hủy) và filter
  cũ chỉ có `is_test_order = FALSE` (audit row 7); sửa có kiểm soát theo quyết định
  BA. Số liệu chuẩn trên seed hiện tại: net_revenue = **3000** (đơn #5 hủy, 400, bị loại),
  order_count = **8**, AOV = **375.0**.

## 2. Bảng quyết định 19 metric (workbook → golden)

Mọi metric tỷ lệ (ratio): `* 1.0 / NULLIF(..., 0)`, `metric_type: derived`,
`aggregation: ratio` — theo khuyến nghị NULLIF trong audit.

| # | metric | Thay đổi so với workbook | Lý do (audit ref) |
|---|--------|--------------------------|-------------------|
| 1 | `net_revenue` | + loại đơn cancelled (`is_canceled = FALSE`); bỏ chữ "thuế" khỏi description | Mâu thuẫn glossary & dữ liệu không có cột thuế; audit row 7 |
| 2 | `order_count` | + `is_canceled = FALSE` (đồng bộ chính sách đơn hợp lệ) | Nhất quán net_revenue; audit row 8 |
| 3 | `average_order_value` | aggregation `avg`→`ratio`; numerator = net sales đơn hợp lệ ⇒ **375.0**; NULLIF | Audit row 9; đồng bộ dependencies |
| 4 | `conversion_rate` | numerator = session `completed_checkout = TRUE`; NULLIF; **bỏ default filter bot** (mục 4) | Audit row 10; quyết định nhóm |
| 5 | `return_rate` → **đổi tên** `returned_order_rate` | Mẫu số = đơn hợp lệ (loại cancelled); NULLIF | Audit row 11 + glossary ("tỷ lệ đơn bị hoàn trả") |
| 6 | `units_sold` | Giữ SQL; description bỏ "(SKU)", ghi rõ gross ordered units | Audit row 12 |
| 7 | `customer_count` | Giữ; description ghi rõ bỏ khách vãng lai (customer_id NULL) | Audit row 13 |
| 8 | `returning_customer_rate` | + NULLIF | Audit row 14 |
| 9 | `cart_abandonment_rate` | + NULLIF | Audit row 15 |
| 10 | `gross_margin` | Net sales theo chính sách đơn hợp lệ (đồng bộ net_revenue mới); NULLIF; kết quả chuẩn **0.3567** | Tránh mâu thuẫn mới với net_revenue |
| 11 | `discount_rate` (MỚI) | RATIO + NULLIF; chuẩn **0.0519** | Workbook row 17 (CUSTOM) |
| 12 | `average_delivery_lead_time_hours` (MỚI; đổi tên từ `average_fulfillment_hours`) | SQL theo dialect (mục 5); filter `is_test_order = FALSE AND is_delivered = TRUE`; chuẩn **36.0** | Audit row 18 |
| 13 | `order_cancellation_rate` (MỚI) | RATIO + NULLIF; mẫu số gồm cả đơn bị hủy (internal, mục 6); chuẩn **0.1111** | Workbook row 19 |
| 14 | `units_per_transaction` (MỚI) | aggregation `ratio` (không `avg`); filter đơn hợp lệ; chuẩn **2.5** | Audit row 20 |
| 15 | `add_to_cart_rate` (MỚI) | RATIO + NULLIF; **không default filter bot** (mục 4); chuẩn **0.6154** | Workbook row 21 |
| 16 | `checkout_abandonment_rate` (MỚI) | RATIO + NULLIF; định nghĩa theo **session** (mục 6) | Audit row 22 |
| 17 | `average_session_duration` (MỚI) | Giữ AVG; **không default filter bot** (mục 4); chuẩn **276.15** giây | Workbook row 23 |
| 18 | `loyalty_order_penetration` (MỚI) | RATIO + NULLIF; chuẩn **0.3333** | Workbook row 24 |
| 19 | `low_stock_sku_count` (MỚI) | Giữ logic; **không tính SKU hết hàng** (`in_stock = TRUE`); chuẩn **2** | Workbook row 25 |

`allowed_dimensions`: metric phía đơn/order-item bổ sung `city.city_name` và
`city.region_name` (phục vụ case L3 multi-hop). `default_time_grain` giữ nguyên
mapping từ workbook (đã đánh dấu contract gap `not_applicable` vì candidate
contract schema-forced `"day"`).

## 3. Bốn level của query cases (39 case = 34 positive + 5 error)

| Level | Difficulty | Định nghĩa | Ví dụ | Số case |
|-------|-----------|------------|-------|---------|
| **L1** Explicit | easy | Tên metric + dimension nêu trực tiếp, nằm ngay catalog | *"Tổng doanh thu thuần?"*, *"Units sold theo product?"* | 16 |
| **L2** Semantic/Implicit | medium | Paraphrase nghiệp vụ; tự phân giải filter (kênh, bot), time grain tháng, hoặc multi-metric cùng entity | *"Tháng vừa rồi trên sàn marketplace bán được bao nhiêu tiền sau trừ giảm giá và hoàn trả?"* (net_revenue + WHERE channel + time grain month) | 12 |
| **L3** Multi-hop Join | hard | Dimension phải đi qua chuỗi JOIN nhiều bảng (fact_orders → customers → customer_addresses → cities) | *"Doanh thu thuần theo thành phố?"* (net_revenue × city.city_name) | 6 |
| **L4** Ambiguous | hard | KHÔNG biên dịch SQL — phải hỏi lại làm rõ; `expected: null`, `expected_error: NEEDS_CLARIFICATION` | *"Tình hình bán hàng tuần này thế nào?"* | 3 |
| (nếu âm) | — | Negative: metric không tồn tại / intent không an toàn (`UNKNOWN_METRIC`, `UNSAFE_INTENT`), `level: null` | *"Chỉ số gợi ý sản phẩm AI?"* | 2 |

Chuỗi FK nhiều-nhiệm-một cho L3 (đúng hình `SemanticQueryCompiler._safe_join_path`
phát bằng BFS): `fact_orders.customer_id → customers.id` →
`customers.default_address_id → customer_addresses.address_id` →
`customer_addresses.city_id → cities.city_id`. Case units_sold L3 xuất phát từ
`fact_order_items` JOIN `fact_orders` trước khi vào chuỗi trên.

## 4. Bỏ default filter `is_bot_traffic` (deviation có chỉ đạo của nhóm)

Workbook gắn default filter `is_bot_traffic = FALSE` cho 4 metric session
(conversion_rate, add_to_cart_rate, checkout_abandonment_rate, average_session_duration).
**Dataset thật của nhóm không có cột này ở lớp mặc định**, nên theo chỉ đạo trực tiếp:
golden để `default_filters: []` cho cả 4 metric, giữ `session.is_bot_traffic` là
dimension lọc ad-hoc (case `query_012` dùng `WHERE is_bot_traffic = FALSE` tường minh).
Đây là deviation so với workbook — ghi rõ để BA đối chiếu khi nâng cấp workbook.

## 5. `average_delivery_lead_time_hours` — SQL theo dialect

Golden SQL phải chạy thật trên từng dialect nên biểu diễn khoảng thời gian khác nhau:

- **sqlite**: `AVG((julianday(delivered_time) - julianday(order_date)) * 24.0)`
- **postgresql**: `AVG(EXTRACT(EPOCH FROM (delivered_time - order_date)) / 3600.0)`
- **mysql**: `AVG(TIMESTAMPDIFF(MINUTE, order_date, delivered_time) / 60.0)` — xấp xỉ
  phút-rồi-chia (MySQL không có HOUR với phần thập phân); lệch nhỏ do làm tròn phút,
  chấp nhận được vì eval execution chỉ chạy trên sqlite.

Đơn #5 bị hủy nên chưa giao ⇒ `delivered_time IS NULL` ⇒ dòng NULL trong nhóm
`delivery_type` khi group by là **đúng ngữ nghĩa**, không phải lỗi seed.

## 6. Internal definitions (chưa có trong workbook — golden tự định nghĩa)

- **checkout_abandonment_rate**: định nghĩa theo **phiên** (session đến bước checkout
  mà không hoàn tất), KHÔNG phải định nghĩa giỏ hàng GA4. Khác `cart_abandonment_rate`
  (entity `cart`, tạo giỏ nhưng không thanh toán) — hai metric đo hai phễu khác nhau.
- **order_cancellation_rate / loyalty_order_penetration**: mẫu số gồm cả đơn bị hủy
  (đo trên tổng đơn phát sinh thật). Nếu BA muốn mẫu số chỉ đơn hợp lệ, sẽ đổi ở
  version sau kèm đổi cả query cases liên quan.
- **low_stock_sku_count**: SKU "sắp hết hàng" = `is_active = TRUE AND in_stock = TRUE
  AND current_stock_quantity <= min_stock_quantity` — SKU **đã hết hàng không tính**
  (hết hàng là state khác, không phải cảnh báo low-stock).
- **AOV = 375.0** (3000/8) — không phải 425: net_revenue mới loại đơn #5 (hủy, 400).
- **`default_time_grain` của `low_stock_sku_count`**: giữ `"day"` theo workbook dù
  không có ý nghĩa nghiệp vụ (snapshot tồn kho) — schema contract không có giá trị
  trống; đã đánh dấu contract gap.

## 7. Quy ước golden SQL (compiler shape)

Golden SQL của 34 case positive được viết **đúng hình đầu ra của
`SemanticQueryCompiler`** để `sql_ast_equivalence` so khớp AST trực tiếp:

- Default filter của metric được **CASE-wrap bên trong aggregate**
  (`SUM(CASE WHEN is_test_order = FALSE AND is_canceled = FALSE THEN ... END)`),
  không phải WHERE.
- JOIN **trần** (`JOIN`, không viết `INNER JOIN` — sqlglot phân biệt kind `None` vs
  `"INNER"`); bảng theo thứ tự BFS của compiler (base table trước, join theo path).
- Không `LIMIT` (compiler auto-append 100; hybrid engine bỏ LIMIT khi so sánh).
- `ORDER BY` giữ nguyên (engine bỏ qua khi normalize).
- Cột group-by giữ qualifier bảng (`cities.city_name AS city_name`); metric name
  luôn là SELECT alias (ràng buộc validator).
- Đơn bảng: canonical hóa sẽ strip qualifier cột; đa bảng: bảng được đổi tên
  `_t1.._tN` theo thứ tự FROM/JOIN — golden dùng đúng thứ tự đó.

## 8. Product gaps cố ý lộ qua benchmark

Các case sau **chấm FAIL có chủ đích** khi chạy agent-live vì sản phẩm chưa hỗ trợ —
giữ để theo dõi khi sản phẩm sửa:

1. **3 case L4 + resolver clarify**: eval resolver đã hỗ trợ `NEEDS_CLARIFICATION`,
   nhưng flow sản phẩm chưa có Query Clarifier node.
2. **`guardrail_014` (`SELECT ... FOR UPDATE`)**: eval validator đã cấm `exp.Lock`
   (mở rộng lockstep v3.0.0); `src/services/query_compiler.py::validate_read_only`
   chưa cấm lock clause ⇒ adapter chấp nhận ⇒ case fail (kỳ vọng).
3. **`expected_preview_facts`**: candidate contract không sinh preview facts
   (adapter để rỗng) ⇒ mọi metric case fail field này (contract gap đã khai báo
   trong manifest `contract_gaps`).

`guardrail_016` (`pg_sleep`) đã được eval chấm và adapter đồng ý từ v3.0.0
(lockstep thêm `pg_sleep` vào cả eval validator và engine normalization).

## 9. Renames & traceability

- `return_rate` → `returned_order_rate`; `average_fulfillment_hours` →
  `average_delivery_lead_time_hours` (tên mới đúng ngữ nghĩa "đặt → giao xong").
- Mọi metric YAML có `ground_truth_source: "...xlsx#<metric>"` anchor về workbook.
- 11 query case clone lặp mẫu đã retire (003, 013, 015, 016, 019, 022, 024, 025,
  027, 028, 030) để lấy chỗ cho case L2 paraphrase / L3 multi-hop / L4 clarify.
