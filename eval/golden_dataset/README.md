# Golden Dataset for AI Semantic Layer Agent Evaluation

Tập dữ liệu Ground Truth do con người xây dựng để đánh giá AI Agent theo kiến trúc
4 Giai đoạn trong `implementation_plan.md`. Trạng thái phê duyệt được khai báo
riêng trong manifest; không mặc định coi mọi version là đã approved.

## Cấu trúc thư mục

```
golden_dataset/
└── ecommerce/                  # Domain Ecommerce MVP
    ├── manifest.json           # Khai báo version, dialects, case file references
    ├── sources/                # DDL Schemas & Seed data cho SQLite, PostgreSQL, MySQL
    ├── raw_schema/             # Inspector raw schema metadata outputs
    ├── canonical/              # Domain, Entity, Metric & Glossary YAMLs (Ground Truth)
    ├── cases/                  # Test cases cho Discovery, Metric, Query & Guardrails
    └── expected_results/       # Normalized Execution Query Results
```

## Supported Dialects
- `sqlite`: Dialect mặc định để chạy execution accuracy in-memory.
- `postgresql`: Dialect sản xuất chính (PostgreSQL schema dumps & dialect SQL queries).
- `mysql`: Dialect sản xuất phụ (MySQL schema dumps & dialect SQL queries).

## Ecommerce v3.0.0

- 19 canonical metrics đồng bộ từ `Ecommerce_Metric_Dictionary_Ground_Truth_Expanded.xlsx`
  (gồm 9 metric mới và 2 rename: `returned_order_rate`, `average_delivery_lead_time_hours`).
- 10 canonical entities: thêm `item`, `address`, `city`; chuỗi L3
  `order → customer → address → city` qua FK many-to-one.
- 4 discovery cases, gồm declared FK và inferred session→order relationship.
- 21 metric-definition cases: 19 ground-truth success và 2 negative cases.
- 39 runtime query cases chia 4 level — L1 16 / L2 12 / L3 6 / L4 3 —
  cộng 2 negative (`UNKNOWN_METRIC`, `UNSAFE_INTENT`); 34 success cases.
- 16 SQL guardrail cases: thêm `FOR UPDATE`, `PRAGMA`, `pg_sleep`
  (lockstep mở rộng `exp.Lock` + `pg_sleep` trong eval validator).
- 34 expected result sets tái lập từ SQLite in-memory fixture
  (`scripts/verify_golden_results.py`).

Canonical registry dùng một thư mục `entities/` và một thư mục `metrics/` duy
nhất. Định nghĩa 4 level, chính sách "đơn hợp lệ", các internal definitions và
product gaps cố ý lộ được ghi tại `ecommerce/GROUND_TRUTH_NOTES.md`.

Dataset đang ở trạng thái `pending` vì toàn bộ metric trong workbook có status `Draft`.

## Validation

```bash
pytest tests/test_evaluation -q
ruff check eval tests/test_evaluation
ruff format --check eval tests/test_evaluation
```
