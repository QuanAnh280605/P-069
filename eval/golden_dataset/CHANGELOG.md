# Golden Dataset Changelog

## [2.0.1] - 2026-08-09
### Changed
- Xóa chín metric legacy vì không có metric-definition cases, query cases hoặc
  expected results tương ứng; baseline chỉ còn 10 metric của nhóm.
- Hợp nhất customer, product và payment vào `canonical/entities/`; không còn
  `metric_extensions`, `entity_extensions` hoặc legacy raw/source directories.
- Bổ sung các support tables, seed data, foreign keys, raw schemas và discovery
  expectations để mọi canonical entity đều có physical mapping hợp lệ.

## [2.0.0] - 2026-08-09
### Changed
- Đồng bộ benchmark chính theo 10 metric trong `Ecommerce_Metric_Dictionary_Ground_Truth.xlsx`.
- Mở rộng contract cho Simple/Derived/RATIO, formula, SQL expression, source table,
  dimensions, time grain, provenance, status và owner.
- Thay fixture bằng bốn fact tables phục vụ đầy đủ revenue, order, session, cart,
  customer-returning và gross-margin scenarios.
- Viết lại 12 metric-definition cases và 32 runtime query cases; giữ 30 success
  result sets có thể tái lập trên SQLite.
- Tạm chuyển entity/metric cũ sang thư mục extension để tách khỏi baseline.
- Giữ trạng thái `pending` vì nguồn Excel đánh dấu cả 10 metric là `Draft`.

## [1.1.0] - 2026-08-09
### Fixed
- Chuẩn hóa raw-schema fixtures theo `src.models.raw_schema.RawSchema`.
- Bổ sung cross-reference validation cho canonical artifacts và expected results.
- Hoàn thiện expected execution results cho toàn bộ success query cases.
- Sửa các query dùng sai canonical Metric và loại bỏ fanout revenue ground truth.
- Bổ sung inferred-FK, negative metric/query và AST guardrail cases.
- Bổ sung NULL, repeated products và time-boundary rows vào SQLite seed data.
- Đánh dấu dataset chờ BA/DA phê duyệt lại sau khi sửa semantic ground truth.

## [1.0.0] - 2026-08-09
### Added
- Khởi tạo Golden Dataset v1.0.0 cho domain `ecommerce`.
- Thêm DDL Schemas & Seed data cho SQLite, PostgreSQL (`schema_dump.sql`), và MySQL (`schema_dump.sql`).
- Thêm Discovery Cases (bao gồm PostgreSQL DDL dump, MySQL DDL dump, và SQLite live inspection).
- Thêm Metric Definition Cases (bao gồm SUM, COUNT, AVG, COUNT_DISTINCT, default_filters).
- Thêm 32 Runtime Query Cases với đầy đủ SQL dialect cho PostgreSQL, MySQL, và SQLite.
- Thêm Guardrail Security Cases kiểm thử chống SQL Injection / Cấm DML, DDL.
- Freeze mốc thời gian đánh giá `frozen_evaluation_date = "2026-08-01T00:00:00Z"`.
