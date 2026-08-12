# Evaluation Framework (Khung đánh giá)

Khung đánh giá **deterministic** (tính toán xác định, không ngẫu nhiên) và **có version**
cho AI Semantic Layer Agent. Khung này chấm điểm các output do agent sinh ra — schema
discovery, enrichment, sinh metric, biên dịch query, và SQL guardrails — dựa trên một
**Golden Dataset** kết quả kỳ vọng, dùng precision/recall/F1 và text similarity tiếng Việt
thay vì đánh giá tự do bằng LLM.

> **Phạm vi PR này (chỉ phần framework):** package `eval/dataset/` và `eval/evaluator/`
> cùng các unit test pure-logic. Golden Dataset fixture và các integration test phụ thuộc
> golden nằm ở PR golden-data xếp chồng (`eval/golden_dataset/`).

---

## Kiến trúc

Hai lớp độc lập, đều async và có type hint đầy đủ.

### 1. Lớp Dataset — `eval/dataset/`

Tải và validate một domain Golden Dataset có version. Mọi contract đều là Pydantic model
strict, frozen (`extra="forbid"`).

| Module | Trách nhiệm |
|--------|-------------|
| `models.py` | Các contract strict: `DomainManifest` và 4 loại case (`DiscoveryCase`, `MetricDefinitionCase`, `QueryCase`, `GuardrailCase`), định nghĩa canonical cho entity/metric/dimension/relationship, và `QueryReferenceCatalog`. Mọi artifact đều mang `dataset_version` + `contract_version`. |
| `loader.py` | `load_domain_dataset(golden_root, domain)` (async) → `DomainDataset`. Tải manifest, 4 bộ case, canonical YAML registry, raw schema, và kết quả query kỳ vọng, sau đó chạy cross-validation đầy đủ. Các tham chiếu đường dẫn được bảo vệ chống path-traversal. |
| `validator.py` | Validate tính toàn vẹn, tham chiếu chéo, và **SQL AST read-only** bằng `sqlglot`. Ép buộc case_id duy nhất toàn cục, dialect coverage khớp manifest, số metric ground-truth khớp registry, chỉ cho phép đúng một `SELECT` không có side-effect, và cấm các hàm nguy hiểm. |

### 2. Lớp Evaluator — `eval/evaluator/`

Chấm điểm các output của agent (candidate output) một cách deterministic so với dataset đã tải.

| Module | Trách nhiệm |
|--------|-------------|
| `schemas.py` | Evaluation contract **v2.0.0**: `EvaluationConfig` (ngưỡng + giới hạn an toàn) và mọi contract kết quả (`MatchCounts`, `PrecisionRecallF1`, `FieldScore`, `CaseEvaluationResult`, `SuiteEvaluationResult`, `GroupScore`, `DomainEvaluationResult`), cùng contract cho candidate output (`CandidateEnrichmentOutput`, `CandidateMetricOutput`, `CandidateCompilerOutput`, `CandidateGuardrailOutput`, `DomainCandidateOutputs`). |
| `scoring.py` | Set matching, precision/recall/F1 (có chính sách zero-division cho tập rỗng được tài liệu hóa rõ), micro/macro averaging, và phát hiện trùng lặp. |
| `text_similarity.py` | So sánh tên tiếng Việt: exact (chuẩn hóa NFC), fuzzy (accent-insensitive bằng `SequenceMatcher`), và một semantic provider tùy chọn có thể inject qua `compare_business_name()`. |
| `sql_normalization.py` | Parse và chuẩn hóa SQL fail-closed bằng `sqlglot`: `normalize_sql()`, `structurally_equal()` (bỏ qua format và alias có thể bỏ đi), `effective_limit()`, và ép buộc read-only. |
| `execution.py` | Thực thi `SELECT` được guard trong SQLite in-memory cô lập: `execute_guarded_sql()` (statement timeout qua progress handler, validate LIMIT/timeout) và `compare_query_result()` (theo thứ tự hoặc multiset, với dung sai float). |
| `aggregation.py` | `build_suite_result()` tổng hợp kết quả từng case thành một `SuiteEvaluationResult` đầy đủ provenance (micro, macro, và group score theo tag). |
| `discovery_eval.py` | Suite đánh giá độ chính xác trích xuất schema ở Stage 1 — chấm tables, columns, primary keys, relationships bằng PRF1 (`evaluate_discovery_suite`). |
| `enrichment_eval.py` | Suite đánh giá enrichment entity/dimension/relationship ở Stage 2. |
| `metric_eval.py` | Suite đánh giá sinh định nghĩa metric ở Stage 3 (ngôn ngữ tự nhiên → `CanonicalMetric`). |
| `compiler_eval.py` | Suite đánh giá biên dịch canonical-query và SQL guardrail ở Stage 4 (`evaluate_compiler_suite`, `evaluate_guardrail_suite`, `GuardrailAdapter`). |
| `domain_eval.py` | Orchestrator. `evaluate_domain_suite()` chạy các suite enrichment, metric, compiler, guardrail và lắp thành `DomainEvaluationResult`; `EvaluationDependencies` inject `TextSimilarityProvider` và `GuardrailAdapter` (tùy chọn). |

### Ánh xạ lifecycle Canonical-model

```
Stage 1  Discovery   (độ chính xác introspect schema)         → discovery_eval
Stage 2  Enrichment  (đặt tên nghiệp vụ, dim, relationship)   → enrichment_eval
Stage 3  Metric      (ngôn ngữ tự nhiên → CanonicalMetric)    → metric_eval
Stage 4  Query       (NL → CanonicalQueryModel → SQL)         → compiler_eval + guardrails
```

> `evaluate_domain_suite()` nối Stage 2–4 và guardrail. Stage 1
> (`evaluate_discovery_suite`) là suite live-mode độc lập.

---

## Public API

```python
from pathlib import Path

from eval.dataset.loader import load_domain_dataset
from eval.evaluator import (
    EvaluationConfig,
    EvaluationDependencies,
    evaluate_domain_suite,
)

dataset = await load_domain_dataset(Path("eval/golden_dataset"), "ecommerce")
deps = EvaluationDependencies(config=EvaluationConfig())
result = await evaluate_domain_suite(dataset, candidates, deps)

result.enrichment   # SuiteEvaluationResult
result.metrics      # SuiteEvaluationResult
result.compiler     # SuiteEvaluationResult
result.guardrails   # SuiteEvaluationResult
```

---

## Nguyên tắc thiết kế

- **Deterministic và không dùng LLM.** Việc chấm điểm dựa trên PRF1 và text similarity.
  Semantic similarity là tùy chọn và được inject — **không** được gọi mặc định, nên
  evaluation không phụ thuộc OpenAI.
- **Contract có version để tái lập.** Contract của dataset và evaluation đều pin theo
  semver, mỗi domain ghi lại `frozen_evaluation_date`.
- **An toàn fail-closed.** `SELECT` read-only được ép buộc bằng `sqlglot` AST ở cả lúc
  validate dataset lẫn lúc thực thi; thực thi chạy trong SQLite in-memory cô lập, có
  statement timeout và `LIMIT` giới hạn trong `[1, 1000]`.
- **Model strict, frozen** (`extra="forbid"`) để loại fixture sai định dạng sớm.
- **Async xuyên suốt** — loader, evaluator, và execution đều là `async`.

---

## Test

`tests/test_evaluation/` — sáu unit test pure-logic, **không phụ thuộc Golden Dataset**,
nên framework có thể verify độc lập:

| Test | Phủ |
|------|-----|
| `test_dataset_validation` | Hành vi validator: SQL read-only, tham chiếu, ID duy nhất. |
| `test_evaluator_schemas` | Validate contract kết quả/config của evaluation. |
| `test_execution_safety` | Thực thi SQLite có guard, timeout, ép LIMIT, so sánh kết quả. |
| `test_scoring` | PRF1, set matching, micro/macro averaging, chính sách tập rỗng. |
| `test_sql_normalization` | So sánh cấu trúc, chuẩn hóa alias, ép read-only. |
| `test_text_similarity` | Logic NFC/fuzzy/semantic tiếng Việt và ngưỡng chấp nhận. |

```bash
pytest tests/test_evaluation/ -v
ruff check src/ tests/ eval/
```
