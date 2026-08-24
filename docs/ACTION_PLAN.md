# 📋 Kế hoạch Hành động & Tiến độ (Action Plan) — P-069

> **Dự án:** AI Semantic Layer Agent  
> **Trạng thái:** Toàn bộ các Epic cốt lõi v1.0 đã hoàn thành 100% và vượt tiến độ.  

---

## 1. Tổng kết Tiến độ Thực hiện các Epics

### 🟢 EPIC 1: Backend Core Services & Ingestion Engines
- [x] **Task 1.1:** Triển khai `SQLAlchemy Inspector` đọc schema Live DB (`src/services/introspection.py`).
- [x] **Task 1.2:** Triển khai `SqlDumpScanner & Parser` phân tích cú pháp DDL đa dialect (`src/services/sql_dump_scanner.py`, `src/services/sql_dump_parser.py`).
- [x] **Task 1.3:** Xây dựng mô hình AI 2-Pass Clustering Schema Enrichment (`src/services/pass1_global_glossary.py`, `src/services/clustering.py`, `src/services/pass2_cluster_enrichment.py`).
- [x] **Task 1.4:** Triển khai `CanonicalBuilderService` chuẩn hóa metadata, Primary Keys, Foreign Keys và `canonical_relationships`.
- [x] **Task 1.5:** Triển khai `MetricDefinitionResolver` và quản lý phiên bản `metric_versions` kèm Audit Trail.
- [x] **Task 1.6:** Hoàn thiện `SemanticQueryCompiler` và AST Guardrails với `sqlglot` (`LIMIT 100`, `timeout = 15s`).
- [x] **Task 1.7:** Triển khai hệ thống xác thực JWT, Bcrypt, Google OAuth và phân quyền RBAC (`src/api/auth.py`).

### 🟢 EPIC 2: Multi-Agent Conversational AI & Clarifier
- [x] **Task 2.1:** Xây dựng LangGraph StateGraph Flow 1 chính với HITL Interrupt (`src/agents/graph.py`).
- [x] **Task 2.2:** Xây dựng Chat Orchestrator Multi-Agent Graph điều phối `chitchat` vs `metric_suggest` (`src/agents/chat_graph.py`).
- [x] **Task 2.3:** Xây dựng Query Clarifier Wizard Graph hỏi đáp làm rõ câu truy vấn từng bước (`src/agents/query_clarifier/graph.py`).
- [x] **Task 2.4:** Đăng ký đầy đủ 25+ REST API endpoints trong `src/api/routes.py` và `src/api/query_clarify_routes.py`.

### 🟢 EPIC 3: Next.js Frontend Single Page Workspace
- [x] **Task 3.1:** Xây dựng Landing Page & Workspace Hub kết nối Live DB và Upload SQL Dump (`frontend/src/app/page.tsx`).
- [x] **Task 3.2:** Phát triển **Data Model View** (quản lý bảng, cột, khóa chính/ngoại, inline edit).
- [x] **Task 3.3:** Phát triển **Metrics Catalog View** (quản lý chỉ số, formula, duyệt metric, xem lịch sử phiên bản Drawer).
- [x] **Task 3.4:** Phát triển **Metric Explorer View** (Visual Query Builder, xem trước SQL, thực thi Live DB, AI Query Modal & Wizard).
- [x] **Task 3.5:** Phát triển **AI Studio View** (Khung chat streaming, highlight cú pháp PrismJS SQL/YAML).
- [x] **Task 3.6:** Phát triển **Export Playground View** (Trình xuất bản JSON/YAML).

### 🟢 EPIC 4: Testing & Quality Assurance
- [x] **Task 4.1:** Bộ Unit Tests cho toàn bộ các Node LangGraph và Chat Graphs (`tests/test_agents/`).
- [x] **Task 4.2:** Bộ Integration Tests cho 25+ API Endpoints (`tests/test_api/`).
- [x] **Task 4.3:** Bộ Unit Tests cho các Core Services: 2-Pass, Clustering, Compiler, Dump Parser, Export (`tests/test_services/`).
- [x] **Task 4.4:** Bộ Unit Tests cho 10 ORM Models và Pydantic Schemas (`tests/test_models/`).
- [x] **Task 4.5:** Kiểm tra Linting và Formatting nghiêm ngặt với Ruff (`ruff check src/`).

### 🟢 FEATURE: Metrics Visual Dashboard (v1.0 — Hoàn thành)
- [x] **Singleton Dashboard Layout:** Bảng `dashboard_layouts` (một layout chung mỗi Semantic Database, khóa `uq_dashboard_layouts_db_id`) + migration Alembic `95ff234b973e`.
- [x] **Strict Schemas & Optimistic Concurrency:** `DashboardWidgetConfig`/`DashboardLayout` schemas + service `save_dashboard_layout` đối chiếu `expected_version`, trả `409 dashboard_version_conflict` khi lệch version.
- [x] **Singleton API:** `GET/PUT /api/v1/semantic/{db_id}/dashboard` (X-Organization-ID header, masking 404, 403, 422, 409).
- [x] **Frontend Contracts & Engine:** `lib/dashboard.ts`, `dashboardApi.ts`, bounded widget query/chart engine (LIMIT ≤ 100, chỉ Live DB `query_supported`, không Text-to-SQL).
- [x] **UI:** Widget config modal, cards, accessible sortable grid (dnd-kit), persistence, empty states, navigation & Explorer drill-down.
- [x] **Verification:** Ruff sạch, pytest backend (1064 passed), ESLint 0 error, Vitest frontend (398 passed), `next build` thành công, round-trip migration trên SQLite cô lập.

---

## 2. Kế hoạch Duy trì & Định hướng Tương lai (Future Roadmap v2.0+)

1. **Direct BI Webhooks & Auto-Sync:** Tự động đồng bộ Semantic Layer đã duyệt lên dbt Cloud và Metabase Data Model qua REST Webhook.
2. **Cross-Database Federation:** Mở rộng Query Compiler để hỗ trợ biên dịch truy vấn liên cơ sở dữ liệu (Cross-DB Joins) an toàn.
3. **Automated Data Profiling Cache:** Bổ sung bộ nhớ đệm thống kê metadata (cardinality, null rate) định kỳ cho Live DB.
