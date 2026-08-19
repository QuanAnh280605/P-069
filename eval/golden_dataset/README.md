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

## Ecommerce v2.0.1

- 10 canonical metrics đồng bộ từ Ecommerce Metric Dictionary Ground Truth.
- 4 discovery cases, gồm declared FK và inferred session→order relationship.
- 12 metric-definition cases: 10 ground-truth success và 2 negative cases.
- 32 runtime query cases: 30 success cases và 2 negative cases.
- 13 SQL guardrail cases, gồm nested DML, `SELECT INTO`, multi-statement và LIMIT policy.
- 30 expected result sets tái lập từ SQLite in-memory fixture.

Canonical registry dùng một thư mục `entities/` và một thư mục `metrics/` duy
nhất. Metric legacy không có benchmark coverage đã được loại bỏ; baseline chỉ
giữ 10 metric từ workbook của nhóm.

Dataset đang ở trạng thái `pending` vì cả 10 metric trong workbook hiện có status `Draft`.
Các khác biệt semantics cần xác nhận được ghi tại
`ecommerce/GROUND_TRUTH_NOTES.md`.

## Validation

```bash
pytest tests/test_evaluation -q
ruff check eval tests/test_evaluation
ruff format --check eval tests/test_evaluation
```
