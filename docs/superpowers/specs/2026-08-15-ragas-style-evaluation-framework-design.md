# Ragas-Style Evaluation Framework with AI-as-Judge — Design Specification

- **Date:** 2026-08-15
- **Status:** Proposed for team review
- **Scope:** Internal technical evaluation and quality assurance
- **Supersedes:** Evaluation reporting and scoring design in
  `2026-08-10-evaluation-framework-design.md`; proven deterministic primitives remain reusable

## 1. Context

The current evaluator is a deterministic, domain-specific scorer for schema discovery,
semantic enrichment, business metric generation, query compilation, and SQL guardrails.
Its existing reports demonstrate framework flow with recorded candidates derived from a
mock Golden Dataset. Those reports are smoke-test evidence, not an independent product
quality benchmark. The production Agent pipeline now emits usable outputs for enrichment,
metric suggestion, query compilation, and execution, so real Agent output must become the
primary candidate source for benchmark and release runs.

The next framework must adopt a Ragas-style evaluation model:

1. One row represents one evaluation sample.
2. Independent metrics score each sample.
3. Results remain available per sample and per metric.
4. Scores aggregate by task, tag, and complete run.
5. AI-as-Judge is supported for subjective semantic criteria.
6. Deterministic checks remain authoritative for security and executable correctness.

## 2. Goals

- Produce trustworthy internal benchmark and release-quality evidence.
- Support deterministic metrics and AI Judge metrics through one result contract.
- Return both an overall score and independent quality-gate decisions.
- Preserve detailed diagnostics for engineering investigation.
- Separate smoke fixtures from independently reviewed benchmark datasets.
- Make runs reproducible through dataset, rubric, prompt, model, and code provenance.
- Reuse tested evaluator logic instead of rewriting SQL and scoring safety primitives.
- Capture candidates directly from real Agent entrypoints without exposing Golden Dataset
  references to candidate generation.

## 3. Non-goals

- Do not use RAG-specific metrics such as context recall or faithfulness when the evaluated
  task has no retrieval context.
- Do not let an AI Judge decide SQL safety, query execution correctness, schema existence,
  row limits, or timeouts.
- Do not treat a self-comparison smoke run as benchmark evidence.
- Do not run free-form Text-to-SQL or execute writes against a target database.
- Do not maintain a separate reporting pipeline for AI Judge results.

## 4. Chosen Approach

Use a **hybrid Ragas-style architecture** with one evaluation pipeline and two metric
executors:

- A deterministic executor wraps the current domain-specific scoring, SQL normalization,
  execution, and guardrail logic.
- An AI Judge executor uses Ragas/custom Ragas metrics behind an adapter and returns the
  same internal `MetricResult` as deterministic metrics.

Ragas is an integration at the metric layer, not the owner of domain orchestration,
quality gates, or final reporting. This keeps the framework Ragas-compatible without
forcing security-critical or complex typed outputs into an LLM-centric abstraction.

```text
Golden Input ----> AgentCandidateProvider ----> Captured Candidate
     |                                            |
     +------------------ case_id -----------------+
                          |
Golden Reference ---------+   (scoring phase only)
                          |
                          v
                  EvaluationSample[]
                |
       +--------+---------+
       |                  |
       v                  v
Deterministic Metrics  AI Judge Metrics
       |                  |
       +--------+---------+
                |
                v
          MetricResult[]
                |
                v
 Aggregation + Quality Gates
                |
                v
       JSON + CSV + Markdown
```

## 5. Reuse Strategy

### 5.1 Reuse with minimal changes

| Existing component | Reuse |
|---|---|
| `eval/evaluator/scoring.py` | Set matching, duplicate detection, PRF1, micro/macro primitives |
| `eval/evaluator/sql_normalization.py` | Read-only validation, normalization, AST equivalence |
| `eval/evaluator/execution.py` | Isolated SQLite execution, result comparison, timeout and limit checks |
| `eval/evaluator/text_similarity.py` | Unicode normalization and deterministic exact/fuzzy similarity |
| Dataset models, loader, validator | Versioning, strict validation, reference integrity, read-only SQL checks |
| Candidate Pydantic models | Typed `response` payloads for task-specific samples |

### 5.2 Adapt into independent metrics

| Existing logic | New metric |
|---|---|
| Discovery table/column/PK/relationship scoring | `TableF1`, `ColumnF1`, `PrimaryKeyAccuracy`, `RelationshipF1` |
| Enrichment entity and dimension scoring | `EntityF1`, `DimensionF1` |
| Business-name comparison | `BusinessNameSimilarity` |
| Metric identity and fields | `MetricIdentityAccuracy`, field-specific metrics |
| Compiler request and selected-field validation | `RequestValidationAccuracy`, `SelectionPreservationAccuracy` |
| SQL structural comparison | `SqlAstEquivalence` |
| Guarded execution comparison | `SqlExecutionAccuracy` |
| Guardrail case comparisons | Four independent guardrail metrics |

### 5.3 Replace

- Replace suite-centric orchestration in `domain_eval.py` with sample-centric metric
  execution.
- Replace current unweighted aggregation with configured metric and suite weights.
- Replace the current top-level result with a run result containing validity, coverage,
  overall score, quality gates, and provenance.
- Replace the summary-only runner output with JSON, flat CSV, and Markdown reporting.
- Retain current recorded self-comparison artifacts only as smoke-test fixtures.

## 6. Core Contracts

### 6.1 Evaluation sample

```json
{
  "sample_id": "ecommerce_query_001",
  "task": "query_compilation",
  "input": {
    "metric_names": ["net_revenue"],
    "dimension_names": ["order_month"],
    "filters": [],
    "limit": 100
  },
  "reference": {
    "sql": "SELECT ...",
    "expected_result": []
  },
  "response": {
    "sql": "SELECT ...",
    "parameters": {},
    "metadata": {}
  },
  "metadata": {
    "tags": ["net_revenue", "medium"],
    "dataset_version": "1.0.0"
  }
}
```

Task-specific Pydantic models validate `input`, `reference`, and `response`. The common
envelope enables a Ragas-style sample table without weakening typed domain contracts.

The candidate-generation process receives only `sample_id`, `task`, `input`, and permitted
metadata. The runner joins `reference` only after candidate capture has completed.

### 6.2 Metric interface

```python
class EvaluationMetric(Protocol):
    name: str
    metric_type: Literal["deterministic", "ai_judge"]

    async def score(
        self,
        sample: EvaluationSample,
        context: EvaluationContext,
    ) -> MetricResult:
        ...
```

### 6.3 Unified metric result

```json
{
  "metric": "business_semantic_correctness",
  "metric_type": "ai_judge",
  "status": "passed",
  "score": 0.85,
  "threshold": 0.8,
  "reason": "The definition matches net revenue after returns and discounts.",
  "details": {
    "business_meaning": 0.9,
    "reference_alignment": 0.85,
    "hallucination_avoidance": 0.8,
    "clarity": 0.8
  },
  "provenance": {
    "rubric_version": "1.0.0",
    "prompt_version": "business-semantics-v1",
    "model": "configured-model"
  }
}
```

Allowed statuses are `passed`, `failed`, `error`, and `not_applicable`. A missing required
metric makes the run incomplete; it is not silently removed from scoring.

### 6.4 Direct Agent candidate acquisition

`AgentCandidateProvider` is the primary provider for benchmark and release runs:

```python
class CandidateProvider(Protocol):
    async def generate(
        self,
        value: EvaluationInput,
        context: CandidateRunContext,
    ) -> CapturedCandidate:
        ...
```

`EvaluationInput` deliberately has no `reference` field. Candidate generation and scoring
are separate phases and may run in separate processes:

```text
Phase A — generation
  load public benchmark inputs
  -> invoke real Agent entrypoints
  -> validate and persist immutable candidate artifacts
  -> close candidate generation

Phase B — scoring
  load candidate artifacts by case_id
  -> load private Golden references
  -> construct EvaluationSamples
  -> run deterministic and AI Judge metrics
```

The provider delegates by task:

| Task | Real Agent entrypoint | Captured candidate |
|---|---|---|
| Discovery | `src.agents.graph.agent` through `introspect_node` | `AgentState.raw_schema` |
| Enrichment | The same graph through `enrich_node` | `AgentState.enriched_schema` |
| Metric suggestion | `on_demand_metric_suggest_node` for schema-wide generation; `generate_metrics_from_prompt` for prompt-specific cases | `suggested_metrics` or typed metric suggestions |
| Compiler | `SemanticQueryCompiler.compile` using selected metric/dimension inputs and an isolated metadata store populated from captured Agent semantic output | compiled SQL, parameters, and compiler metadata |
| Query execution | `execute_compiled_query` against the benchmark's isolated live SQLite target | columns, rows, and row count |
| Guardrails | The real read-only validator/compiler boundary used by Flow 2 | acceptance, transformed SQL/limit/timeout, or error code |

The Flow 1 graph is invoked only through the point required by the case. Evaluation capture
stops before the HITL save node unless persistence is part of the scenario. Compiler cases
use an isolated metadata store and never write to the target database.

Adapters translate captured application output into evaluator candidate models; they must
not repair, enrich, or default a semantically invalid Agent result. Mapping failures become
explicit candidate errors.

Every captured candidate records:

- `candidate_source = "agent_live"` or `"agent_recorded"`.
- Source commit and Agent/prompt/model versions.
- Task entrypoint and configuration.
- Generation timestamp, latency, token usage, and error metadata.
- A content hash used for immutable replay and judge caching.

Recorded mode remains supported, but it replays previously captured **real Agent output**.
Golden-derived recorded candidates are allowed only under `run_type="smoke"` and cannot
produce a valid benchmark or release score.

Two evaluation profiles are supported:

- `pipeline`: primary end-to-end profile. Each downstream stage consumes the actual output
  of the preceding Agent stage, so upstream errors propagate honestly.
- `component`: diagnostic profile. A stage receives reviewed upstream fixtures but still
  generates its own candidate; this isolates the quality of that stage. Component scores
  cannot replace the pipeline release gate.

## 7. Metric Catalog

### 7.1 Discovery

- `table_precision`, `table_recall`, `table_f1`
- `column_f1`
- `primary_key_accuracy`
- `relationship_f1`

All Discovery metrics are deterministic.

### 7.2 Enrichment

- `entity_f1`
- `dimension_f1`
- `relationship_accuracy`
- `business_name_similarity`
- `business_semantic_correctness` — AI Judge

### 7.3 Business metric generation

- `metric_identity_accuracy`
- `formula_equivalence`
- `sql_expression_equivalence`
- `filter_accuracy`
- `allowed_dimension_f1`
- `business_definition_correctness` — AI Judge
- `formula_semantic_correctness` — AI Judge

### 7.4 Query compiler

- `request_validation_accuracy`
- `selection_preservation_accuracy`
- `sql_ast_equivalence`
- `sql_execution_accuracy`
- `result_schema_accuracy`
- `invalid_selection_rejection`

The product's Flow 2 starts from explicit Metric and Dimension selections and compiles them
deterministically. It does not perform free-form natural-language-to-CQM generation, so the
Compiler suite has no CQM or AI Judge metric.

### 7.5 Guardrails

- `unsafe_sql_rejection`
- `valid_select_acceptance`
- `limit_enforcement`
- `timeout_enforcement`
- `error_code_accuracy`

All Guardrail metrics are deterministic and critical.

## 8. AI-as-Judge Design

AI Judge metrics are part of the same metric registry and result schema. They run through
a separate execution lane so concurrency, retries, caching, latency, token usage, and cost
can be controlled independently.

### 8.1 Judge input

Each judge receives only:

- The task request.
- Minimal relevant schema context.
- A reviewed reference and explicit rubric.
- The candidate response.

The judge does not receive the candidate model name, experiment label, deterministic
scores, baseline score, or release decision.

### 8.2 Judge rules

- Obtain the model through `get_llm()`; never instantiate `ChatOpenAI` directly.
- Use temperature `0.0`.
- Require structured output validated by Pydantic.
- Store concise reasons, not chain-of-thought.
- Cache by sample, candidate content, rubric version, prompt version, and model.
- Treat timeout, invalid output, or exhausted retries as metric `error`.
- Route borderline or conflicting cases to manual review.

### 8.3 Judge rubric

Default semantic rubric:

| Criterion | Weight |
|---|---:|
| Business meaning correctness | 40% |
| Alignment with reference and schema | 25% |
| Absence of unsupported assumptions | 20% |
| Clarity | 15% |

AI Judge contributes no more than 30% of Enrichment and 25% of Business Metrics. It
contributes 0% to Discovery, Compiler, and Guardrails.

## 9. Scoring and Quality Gates

### 9.1 Suite weights

| Suite | Overall weight | Default minimum |
|---|---:|---:|
| Discovery | 15% | 0.95 |
| Enrichment | 20% | 0.85 |
| Business Metrics | 25% | 0.85 |
| Compiler | 25% | 0.90 |
| Guardrails | 15% | 0.95 |

The overall score is the weighted mean of required suite scores. It is reported on a
0–100 scale. A score is marked valid only when required coverage and provenance gates pass.

### 9.2 Run status

| Status | Rule |
|---|---|
| `PASS` | Score is valid, overall score is at least 90, and every gate passes |
| `WARN` | Score is valid, overall score is from 80 to below 90, and no critical gate fails |
| `FAIL` | An observed critical gate fails, or a valid overall score is below 80 |
| `INCOMPLETE` | No critical failure was observed, but a required metric is unavailable, coverage is below 95%, or benchmark validity fails |

Status precedence is `FAIL` for an observed critical failure, then `INCOMPLETE` for an
invalid or insufficient run, followed by score-based `PASS`, `WARN`, or `FAIL`. If a hard
deterministic failure makes an AI Judge call unnecessary, the judge metric is recorded as
`not_applicable` with the prerequisite failure as its reason; the observed hard failure
still determines the run status.

Critical gates:

- Security-negative Guardrail cases must pass 100%.
- Compiler execution accuracy must be at least 95% and available.
- Evaluator error count must be zero for a release run.
- Required negative cases cannot be skipped.
- The Golden Dataset must be frozen, independently produced, and approved.
- Candidate generation must not read benchmark references.

A high AI Judge score or high overall score never overrides a critical failure.

## 10. Run Types and Dataset Integrity

| Run type | Purpose | Can support a quality claim? |
|---|---|---|
| `smoke` | Validate framework flow with synthetic or self-derived candidates | No |
| `benchmark` | Score direct or replayed real Agent candidates against an independent reviewed dataset | Yes |
| `release` | Run the direct Agent pipeline and enforce all mandatory quality gates | Yes |

Benchmark data must be separated from framework unit-test fixtures. Every run records:

- Dataset and contract versions.
- Dataset approval and frozen date.
- Evaluator and rubric versions.
- Source commit and environment.
- Candidate model and prompt versions when applicable.
- Judge model, prompt, and rubric versions.
- Candidate source and evaluation profile (`pipeline` or `component`).

A release run requires `candidate_source="agent_live"` and `profile="pipeline"`. A replayed
real Agent candidate may support reproducible benchmark analysis, but not the final release
decision.

## 11. Aggregation and Reporting

The framework aggregates results by:

- Sample.
- Metric.
- Task/suite.
- Tag and difficulty.
- Complete run.

It also calculates coverage, error rate, status counts, and regression against a named
baseline. Results are emitted in three forms:

1. JSON containing the complete run contract and diagnostics.
2. CSV where each row is a sample and each metric is a score column.
3. Markdown containing validity, overall score, gates, suite/metric summaries, failures,
   regressions, and recommendations.

Top-level output:

```json
{
  "run_id": "eval-20260815-001",
  "run_type": "benchmark",
  "status": "PASS",
  "score_valid": true,
  "overall_score": 92.4,
  "coverage": 0.98,
  "suite_scores": {},
  "metric_summary": {},
  "quality_gates": [],
  "samples": [],
  "provenance": {}
}
```

## 12. Execution Flow

```text
Load and validate public benchmark inputs
  -> invoke AgentCandidateProvider without references
  -> capture immutable real Agent outputs
  -> load private Golden references
  -> join inputs, references, and candidates by case_id
  -> construct typed EvaluationSamples
  -> select metrics by task
  -> run deterministic metrics
  -> stop unnecessary judge calls after critical structural failures
  -> run eligible AI Judge metrics
  -> normalize all MetricResults
  -> aggregate scores and coverage
  -> apply quality gates
  -> compare with baseline
  -> write JSON, CSV, and Markdown reports
```

Recorded real Agent output can be reevaluated without calling the product, target database,
or LLM again. Live Agent generation and scoring remain separate stages. A report explicitly
identifies direct, replayed, or Golden-derived candidates so these evidence levels cannot be
confused.

## 13. Error Handling and Safety

- Dataset contract errors stop the run before scoring.
- A metric failure is isolated and returned as `MetricResult(status="error")`.
- Partial results are preserved, but required metric errors produce `INCOMPLETE` or `FAIL`
  according to run type.
- SQL execution remains SELECT-only, uses isolated SQLite fixtures, applies a 15-second
  timeout, defaults to LIMIT 100, and never exceeds LIMIT 1000.
- SQL Dump inputs are schema-only and never queried.
- Connection URLs and secrets are never stored in reports.
- AI Judge retries are bounded and do not fall back to unvalidated free-form output.

## 14. Testing and Judge Calibration

### 14.1 Framework tests

- Unit tests for every metric.
- Contract tests for sample, result, configuration, and report schemas.
- Integration tests using SQLite in-memory and mocked LLMs.
- Compatibility tests proving migrated deterministic metrics reproduce current scores.
- Anti-self-comparison tests where deliberately corrupted candidates must fail.
- Meta-evaluation tests covering perfect, partially correct, invalid, and adversarial cases.

### 14.2 AI Judge calibration

1. Domain experts label 30–50 representative samples.
2. The judge scores the same blinded samples.
3. Measure agreement, correlation, false-pass rate, and false-fail rate.
4. Revise rubric and prompt until acceptance criteria are met.
5. Freeze prompt and rubric versions.
6. Recalibrate after changing judge model, prompt, rubric, or domain.

Borderline scores and judge/deterministic conflicts are marked `manual_review`; they do not
silently pass a release gate.

## 15. Delivery Plan

### Phase 1 — Contracts and catalog

- Define sample, metric result, run result, metric configuration, and provenance contracts.
- Freeze task, metric, weight, threshold, and critical-gate catalogs.

### Phase 2 — Dataset separation

- Retain current self-derived candidates as smoke fixtures.
- Build and approve an independent benchmark dataset.
- Add negative, boundary, and adversarial cases plus leakage controls.
- Split public generation inputs from private scoring references.

### Phase 3 — Direct Agent capture

- Implement `AgentCandidateProvider` and task-specific Agent drivers.
- Invoke the Flow 1 graph, metric-generation service, compiler, execution service, and real
  guardrail boundary through application entrypoints.
- Capture immutable candidate bundles with provenance before loading references.
- Support primary `pipeline` and diagnostic `component` profiles.

### Phase 4 — Ragas-style metric engine

- Implement metric protocol, registry, task routing, execution context, and error isolation.
- Support deterministic and AI Judge executor types.

### Phase 5 — Deterministic migration

- Wrap existing scoring, enrichment, metric, compiler, execution, and guardrail logic.
- Verify score compatibility with the current evaluator.

### Phase 6 — Ragas and AI Judge integration

- Add and pin the Ragas dependency.
- Implement the `get_llm()` adapter, structured judge metrics, cache, timeout, and retry.
- Add business-semantic, formula-semantic, and intent-alignment metrics.

### Phase 7 — Aggregation and gates

- Implement weighted suite/overall scores, coverage, error rate, run status, critical gates,
  and baseline regression checks.

### Phase 8 — Reporting

- Implement versioned JSON, flat CSV, and team-facing Markdown reports.

### Phase 9 — Verification and calibration

- Complete unit, contract, integration, compatibility, adversarial, and calibration tests.
- Run the old and new evaluators in parallel and explain every material difference.

### Phase 10 — Adoption

- Establish an approved baseline.
- Add benchmark and release profiles to CI.
- Deprecate the legacy orchestrator only after the new framework is stable.

## 16. Acceptance Criteria

- A sample can be scored by deterministic and AI Judge metrics in one run.
- A benchmark/release candidate is obtained from real Agent output and never cloned from a
  Golden reference.
- Candidate generation can execute with no access to the private reference payload.
- Discovery, enrichment, metric, compiler, execution, and guardrail outputs are captured
  through explicit application adapters.
- All metric implementations return the unified `MetricResult` contract.
- Reports include overall score, score validity, coverage, suite scores, metric summaries,
  gates, per-sample results, and provenance.
- A critical Guardrail failure produces `FAIL` regardless of overall or judge score.
- A missing required suite or unapproved benchmark produces `INCOMPLETE`.
- The current deterministic evaluator logic is covered by compatibility tests.
- No production test calls a real LLM unintentionally; unit and integration tests mock it.
- AI Judge has documented calibration evidence before it becomes a release gate.
- Smoke results cannot be presented as benchmark or release results.
- Release reports require direct Agent candidates and the end-to-end pipeline profile.

## 17. Recommended Implementation Order

1. Contracts and metric catalog.
2. Independent benchmark dataset.
3. Direct Agent candidate capture with reference isolation.
4. Metric engine and deterministic adapters.
5. Aggregation, gates, and reporting.
6. Ragas/AI Judge integration.
7. Judge calibration.
8. Parallel migration and CI adoption.

This order makes deterministic benchmark evidence trustworthy before adding the cost and
variability of AI Judge evaluation.
