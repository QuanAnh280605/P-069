# Architecture Document — AI Semantic Layer Agent

## 1. System Overview

Hệ thống **AI Semantic Layer Agent** là nền tảng quản trị và khai thác ngữ nghĩa dữ liệu doanh nghiệp tập trung, giải quyết khoảng cách giữa cấu trúc kỹ thuật (Technical Schema) và ngữ cảnh kinh doanh (Business Context). Hệ thống bao gồm **2 luồng cốt lõi (Core Pipelines)** cùng **2 đồ thị AI hội thoại thông minh (Conversational AI Graphs)**:

- **Flow 1 — Generate & Manage Semantic Layer (Live DB & SQL Dump):**
  - **Schema Ingestion:** Hỗ trợ cả kết nối Live Database (qua SQLAlchemy Inspector) và tải lên file SQL Dump DDL (PostgreSQL, MySQL, SQLite) thông qua bộ phân tích `SqlDumpScanner & Parser`.
  - **2-Pass Hierarchical & Clustering Enrichment:**
    - *Pass 1:* Xây dựng bảng chú giải thuật ngữ toàn cục (Global Domain Glossary).
    - *Clustering:* Phân nhóm đồ thị bảng theo miền nghiệp vụ (Domain Clustering) để tối ưu xử lý schema lớn.
    - *Pass 2:* Sinh tên nghiệp vụ tiếng Việt (`business_name`) và mô tả chi tiết (`description`) cho từng bảng và cột theo cụm, đi kèm cơ chế Fallback tự động.
  - **Canonical Semantic Layer Builder:** Tự động chuẩn hóa metadata, xác định Primary Keys, Foreign Keys, Time Dimensions, quan hệ liên bảng (`canonical_relationships`) và đề xuất Business Metrics ban đầu.
  - **HITL Governance & Versioning:** Member gửi metric ở trạng thái `unverified`; Data Lead xem xét, chỉnh sửa, phê duyệt thành `approved` và quản lý lịch sử phiên bản (`metric_versions`).
  - **Export:** Đóng gói xuất Semantic Layer ra chuẩn JSON và YAML phục vụ tích hợp công cụ BI.

- **Flow 2 — Deterministic Semantic Query Engine (CHỈ DÙNG CHO LIVE DB):**
  - **Deterministic Compilation:** Người dùng chọn Metrics, Dimensions và Filters từ giao diện trực quan; `SemanticQueryCompiler` và `MetricDefinitionResolver` biên dịch thành câu lệnh SQL 100% chuẩn xác dựa trên `canonical_relationships` và metric templates.
  - **Compile-Only Preview:** Cho phép kiểm tra câu lệnh SQL được sinh ra và chẩn đoán cấu trúc mà không cần kết nối/thực thi trên Target DB.
  - **Security Guardrails:** Tích hợp `sqlglot` kiểm tra AST (ép duy nhất lệnh `SELECT`, chặn hoàn toàn `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`), tự động inject `LIMIT 100` (tối đa 1000 rows) và gán `statement_timeout = 15s`.
  - **Read-Only Execution:** Thực thi an toàn trên Live Database và trả về bảng kết quả dạng JSON.

- **Conversational & Interactive Layer:**
  - **Chat Orchestrator Graph:** Tự động phân loại Intent giữa trò chuyện chung (`chitchat_node`) và yêu cầu định nghĩa chỉ số nghiệp vụ (`on_demand_metric_suggest_node`).
  - **Query Clarifier Wizard Graph:** Hỗ trợ người dùng làm rõ các câu truy vấn phức tạp hoặc còn mơ hồ qua từng bước gợi ý thông minh (`wizard_init` $\rightarrow$ `wizard_step` $\rightarrow$ `resolve`).

---

## 2. Architecture Diagram

```mermaid
graph TB
    subgraph Client["🖥️ Client Layer — Next.js 14 Web App"]
        V1["📊 Data Model View\n(Tables, Columns, Relationships)"]
        V2["📋 Metrics Catalog View\n(Submissions, Versions, Approvals)"]
        V3["🔍 Metric Explorer View\n(Visual Query Builder & Live Table)"]
        V4["💬 AI Studio View\n(Multi-agent Streaming Chat & SQL Preview)"]
        V5["📤 Export Playground View\n(JSON / YAML Exporter)"]
        V6["📊 Metrics Dashboard View\n(Shared Singleton Layout, Widgets, Drill-down)"]
    end

    subgraph API["🌐 API Layer — FastAPI (Async REST Endpoints)"]
        AUTH_API["🔐 Auth & Workspace Routes\nJWT, OAuth, invitations, workspace RBAC"]
        INGEST_API["📥 Schema Ingestion Routes\n/semantic/import/* & /semantic/db/*"]
        CATALOG_API["📚 Catalog & Edit Routes\n/semantic/{db_id}/catalog, /table, /column"]
        METRIC_API["🎯 Metric Lifecycle Routes\n/semantic/{db_id}/metrics, /approve, /history"]
        QUERY_API["⚡ Query Engine Routes\n/semantic/{db_id}/query/compile & /query"]
        DASH_API["📊 Dashboard Routes\n/semantic/{db_id}/dashboard (GET/PUT singleton)"]
        AGENT_API["🤖 Conversational & Wizard Routes\n/semantic/{db_id}/chat & /query/clarify/*"]
        EXPORT_API["📦 Export Routes\n/semantic/{db_id}/export?format=json|yaml"]
    end

    subgraph Flow1["⚙️ Flow 1 — Ingestion & 2-Pass Enrichment Pipeline"]
        G_INGEST["Introspect Engine / SQL Dump Scanner\nExtract technical tables, cols, types, FKs"]
        G_PASS1["Pass 1: Global Domain Glossary\nLLM trích xuất thuật ngữ cốt lõi"]
        G_CLUSTER["Domain / Graph Clustering\nPhân cụm bảng theo liên kết FK"]
        G_PASS2["Pass 2: Cluster Enrichment\nLLM sinh business_name & description tiếng Việt\n+ Fallback Generator"]
        G_CANONICAL["Canonical Builder Service\nBuild canonical tables, columns, relationships"]
        HITL["👤 Metric Review & Approval\nData Lead phê duyệt, chỉnh sửa inline"]
        G_PERSIST["Save & Persistence Service\nPersist vào Metadata Store"]

        G_INGEST --> G_PASS1 --> G_CLUSTER --> G_PASS2 --> G_CANONICAL --> HITL --> G_PERSIST
    end

    subgraph Flow2["🔍 Flow 2 — Deterministic Semantic Query Engine (Live DB Only)"]
        Q_RESOLVE["MetricDefinitionResolver\nLoad MetricDefinition v2 & Canonical Relationships"]
        Q_COMP["SemanticQueryCompiler\nResolve joins & compile deterministic SQL"]
        Q_GUARD["SQLGuardrailNode (sqlglot)\n1. Assert SELECT-only AST\n2. Inject LIMIT 100\n3. Set timeout 15s"]
        Q_EXEC["Live DB Execution Service\nRead-Only SELECT Execution on Live DB"]

        Q_RESOLVE --> Q_COMP --> Q_GUARD --> Q_EXEC
    end

    subgraph MultiAgent["🧠 Conversational & Clarifier Agents"]
        CHAT_ORCH["Chat Orchestrator Graph\norchestrator -> chitchat | metric_suggest"]
        WIZARD_ORCH["Query Clarifier Wizard Graph\nwizard_init -> wizard_step -> resolve"]
    end

    subgraph Data["🗄️ Data Layer"]
        METADB[("🗄️ Metadata Store (PostgreSQL / SQLite)\nAuth, workspace RBAC, semantic metadata,\nmetric lifecycle, versions and chat history")]
        TARGET[("🎯 Target Database (Live DB Only)\nPostgreSQL / MySQL / SQLite")]
    end

    Client --> API
    V6 --> DASH_API
    API --> Flow1
    API --> Flow2
    DASH_API --> Flow2
    API --> MultiAgent

    G_INGEST -.->|"Read Schema Only"| TARGET
    G_PERSIST -->|Persist Metadata| METADB
    Q_RESOLVE -->|Read Semantic Definitions| METADB
    Q_EXEC -->|"Execute Read-Only SELECT (LIMIT 100)"| TARGET
```

---

## 3. Detailed Component Workflows

### 3.1. Flow 1: 2-Pass Hierarchical & Clustering Enrichment Pipeline

```mermaid
flowchart TD
    SOURCE(["Nguồn dữ liệu: Live Connection URL hoặc SQL Dump File"]) --> PARSE

    subgraph Ingestion["1. Schema Ingestion"]
        PARSE["SQLAlchemy Inspector (Live DB)\nhoặc SqlDumpScanner & Parser (Dump File)\nOutput: RawSchemaMetadata"]
    end

    subgraph Enrichment["2. 2-Pass AI Enrichment Engine"]
        PARSE --> P1["Pass 1: Global Domain Glossary\nLLM phân tích toàn bộ tên bảng/cột\nđể định hình miền nghiệp vụ chính"]
        P1 --> CLUST["Domain Clustering\nNhóm bảng theo đồ thị quan hệ FK\n(Tối ưu ngữ cảnh cho DB lớn)"]
        CLUST --> P2["Pass 2: Cluster-level Schema Enrichment\nLLM gán business_name & description tiếng Việt\n(Kèm Fallback Name Generator nếu LLM gặp sự cố)"]
    end

    subgraph Canonical["3. Canonical Standardization"]
        P2 --> CANON["Canonical Builder Service\n- Xác định PK, FK, Time Dimension\n- Tự động tạo Canonical Relationships\n- Sinh MetricDefinition v2 mặc định"]
    end

    subgraph HITL_Loop["4. HITL Review & Approval"]
        CANON --> REVIEW{"👤 HITL Review (Web UI)\nData Lead kiểm tra schema, chỉnh sửa\nvà duyệt Metric"}
        REVIEW -->|"Sửa inline"| EDIT["PUT /table hoặc PUT /column\nLưu thay đổi ngay lập tức"]
        EDIT --> REVIEW
        REVIEW -->|"Duyệt (Approve)"| SAVE["Save Node / Persistence Service\nLưu vào PostgreSQL Metadata Store"]
        REVIEW -->|"Yêu cầu sinh lại"| P2
    end

    SAVE --> EXPORT(["✅ Semantic Layer Ready\nExport JSON / YAML hoặc truy vấn Flow 2"])
```

---

### 3.2. Flow 2: Deterministic Semantic Query Pipeline (Live DB Only)

```mermaid
flowchart TD
    REQ(["Payload: Metric IDs, Dimension Columns, Filters, Time Grains"]) --> CHECK_SRC

    CHECK_SRC{"Kiểm tra nguồn DB\n(Live DB hay SQL Dump?)"}
    CHECK_SRC -->|"SQL Dump"| ERR(["❌ HTTP 400 Bad Request\nChỉ hỗ trợ Live DB có kết nối thực"])
    CHECK_SRC -->|"Live DB"| RESOLVE

    subgraph Compilation["1. Semantic Query Compilation"]
        RESOLVE["MetricDefinitionResolver\nĐọc MetricDefinition v2 từ Metadata Store\nvà xác định Base Entity"] --> JOIN_GRAPH
        JOIN_GRAPH["Graph Join Resolver\nTìm đường đi ngắn nhất giữa các bảng\ndựa trên CanonicalRelationshipModel"] --> COMPILE
        COMPILE["SemanticQueryCompiler\nBiên dịch câu lệnh SQL chuẩn dialect (Postgres/MySQL/SQLite)\nvới đầy đủ Dimensions, Aggregations, GROUP BY"]
    end

    subgraph Guardrails["2. AST Security & Guardrails"]
        COMPILE --> PREVIEW_CHECK{"Chế độ\nCompile Preview?"}
        PREVIEW_CHECK -->|"Có"| RET_PREVIEW(["✅ Trả về Compiled SQL & Diagnostics\n(Không thực thi DB)"])
        PREVIEW_CHECK -->|"Thực thi"| GUARD["SQLGuardrailNode (sqlglot)\n1. Kiểm tra AST: Bắt buộc duy nhất SELECT\n2. Chặn INSERT, UPDATE, DELETE, DROP, ALTER\n3. Auto inject LIMIT 100 (max 1000)\n4. Gán statement_timeout = 15s"]
    end

    subgraph Execution["3. Safe Live Execution"]
        GUARD --> DECRYPT["Decrypt Fernet Connection URL\ntrong bộ nhớ RAM"]
        DECRYPT --> EXEC["Live DB Execution Service\nThực thi câu SQL Read-Only trên Target DB"]
        EXEC --> FORMAT["Đóng gói Result Grid (Columns, Rows, Execution Time)"]
    end

    FORMAT --> RES(["✅ Render Data Table & Visualization trên UI"])
```

---

### 3.3. Conversational Multi-Agent & Query Clarifier Graphs

#### A. Chat Orchestrator Graph (`src/agents/chat_graph.py`)
```mermaid
flowchart LR
    MSG(["Tin nhắn của người dùng"]) --> ORCH["orchestrator_node\n(Phân loại ý định Intent)"]
    ORCH -->|"chitchat"| CHIT["chitchat_node\n(Trả lời câu hỏi tổng quan / chào hỏi)"]
    ORCH -->|"metric_query"| METRIC["on_demand_metric_suggest_node\n(Gợi ý MetricDefinition v2 & SQL)"]
    CHIT --> FIN(["Kết thúc lượt hội thoại"])
    METRIC --> FIN
```

#### B. Query Clarifier Wizard Graph (`src/agents/query_clarifier/graph.py`)
```mermaid
flowchart LR
    INPUT(["Câu hỏi truy vấn tự nhiên"]) --> W_INIT["wizard_init_node\n(Phân tích câu hỏi, xác định độ mơ hồ)"]
    W_INIT --> W_STEP["wizard_step_node\n(Đặt câu hỏi làm rõ từng bước)"]
    W_STEP -->|"Cần thêm thông tin"| W_STEP
    W_STEP -->|"Đã đủ ngữ cảnh"| RESOLVE["resolve_node\n(Đóng gói cấu hình Metric & Dimension chuẩn)"]
    RESOLVE --> OUT(["Chuyển sang Semantic Query Explorer"])
```

---

### 3.4. Visual Dashboard — Shared Singleton Layout (Live DB Only)

```mermaid
flowchart TD
    OPEN(["Mở Metrics Dashboard View từ Workspace Sidebar"]) --> LOAD
    LOAD["GET /semantic/{db_id}/dashboard\nTrả về singleton layout (hoặc version-0 rỗng)"] --> CHECK

    CHECK{"catalog.query_supported?\n(Live DB hay SQL Dump?)"}
    CHECK -->|"SQL Dump"| DUMP(["❌ Không query\nHiển thị trạng thái SQL Dump, không compile/execute"])
    CHECK -->|"Live DB"| RENDER

    subgraph Widgets["1. Bounded Widget Engine (mỗi card)"]
        RENDER["Render từng Widget (KPI / Line / Area / Bar / Pie / Table)"] --> COMPILE
        COMPILE["compileSemanticQueryApi\nLấy label & chẩn đoán (không thực thi)"] --> EXEC
        EXEC["executeSemanticQueryApi\nSELECT read-only, LIMIT <= 100, timeout 15s\n(chỉ metric approved, không Text-to-SQL)"]
    end

    EXEC --> PERSIST
    PERSIST["PUT /semantic/{db_id}/dashboard\nLưu singleton layout (optimistic concurrency)"]

    subgraph Concurrency["2. Optimistic Concurrency & All-Role Editing"]
        PERSIST --> VER["Kiểm tra expected_version == stored version"]
        VER -->|"Khớp"| SAVE["Lưu version = expected_version + 1"]
        VER -->|"Lệch"| CONFLICT(["❌ 409 dashboard_version_conflict\n{current_version} — hiển thị banner, tải bản mới / ghi đè"])
    end
```

**Quy tắc an toàn cốt lõi của Dashboard:**

1. **Singleton chia sẻ (Shared Singleton):** Mỗi Semantic Database có đúng một hàng `dashboard_layouts` (khóa `uq_dashboard_layouts_db_id`). Layout là tài sản chung của toàn Workspace, không lưu trên `localStorage` và không phân biệt người dùng — mọi thay đổi đều hiển thị cho tất cả thành viên.
2. **Live-DB-only execution:** Dashboard chỉ gọi `compileSemanticQueryApi` / `executeSemanticQueryApi` khi `catalog.query_supported = true` (Live DB). Với SQL Dump, Dashboard hiển thị trạng thái riêng và **không bao giờ** phát sinh bất kỳ lệnh compile/execute nào.
3. **Approved-only & Deterministic:** Chỉ các metric có `status = approved`, định nghĩa v2 và không có diagnostics mới khả dụng; mỗi widget biên dịch qua `SemanticQueryCompiler` (không dùng Text-to-SQL tự do). Mọi truy vấn chạy qua `executeSemanticQueryApi` nên thừa hưởng guardrail `sqlglot` (SELECT-only, `LIMIT <= 100`, `statement_timeout = 15s`).
4. **All-role shared editing:** Mọi vai trò Workspace (`admin`, `data_lead`, `member`) đều có thể sửa Dashboard chia sẻ, với điều kiện là thành viên Workspace và có quyền `can_query`. Database cá nhân chỉ cho phép người tạo; database Workspace không có header org dùng membership đơn lẻ; database ngoài org bị che thành 404.
5. **Optimistic concurrency:** Mỗi `PUT` mang `expected_version`. Nếu không khớp với version đang lưu, backend trả `409` với payload ổn định `{"code": "dashboard_version_conflict", "current_version": <int>}`; xung đột hiển thị rõ ràng và có thể phục hồi (tải bản mới hoặc ghi đè sau khi tải lại), không áp dụng last-write-wins thầm lặng.

---

## 4. Tech Stack Specification

| Thành phần / Tầng | Công nghệ / Thư viện | Phiên bản | Vai trò & Lý do lựa chọn |
|---|---|---|---|
| **API Framework** | **FastAPI** | $\ge 0.115$ | Xử lý bất đồng bộ (Async IO), OpenAPI auto docs, hiệu năng cao |
| **ASGI Server** | **Uvicorn** | $\ge 0.34$ | ASGI server tiêu chuẩn, hỗ trợ hot-reload trong môi trường phát triển |
| **Data Validation** | **Pydantic v2** | $\ge 2.10$ | Ép kiểu dữ liệu request/response nghiêm ngặt, serializing nhanh |
| **Configuration** | **pydantic-settings** | $\ge 2.7$ | Nạp cấu hình từ `.env` với Type Hints đầy đủ |
| **Agent Orchestration** | **LangGraph** | $\ge 0.2$ | StateGraph điều phối luồng xử lý đa tác tử và cơ chế HITL Interrupt |
| **LLM Framework** | **LangChain** | $\ge 0.3$ | Prompt templates và abstractions tương tác mô hình |
| **LLM Provider** | **OpenAI GPT-4o-mini** | API | Chi phí tối ưu, output đồng nhất với `temperature = 0.0` |
| **Database ORM & Metadata** | **SQLAlchemy** | $\ge 2.0$ | AsyncEngine/Session ORM kết hợp Inspector API đọc schema |
| **SQL Parser & Guardrails** | **sqlglot** | $\ge 25.0$ | Phân tích cú pháp SQL AST, xác thực Read-Only, inject LIMIT & Timeout |
| **Database Migrations** | **Alembic** | $\ge 1.14$ | Quản lý lịch sử thay đổi cấu trúc Metadata Store an toàn |
| **Metadata Database** | **PostgreSQL / SQLite** | 16-alpine | PostgreSQL cho Production/Docker và SQLite cho môi trường test nhanh |
| **Database Drivers** | **asyncpg**, **aiosqlite**, **psycopg2** | Standard | Driver async cho PostgreSQL và SQLite |
| **Security & Auth** | **cryptography (Fernet)**, **python-jose**, **passlib (bcrypt)** | Standard | Mã hóa đối xứng Connection URL; băm mật khẩu và JWT token |
| **Export Formats** | **PyYAML**, **json** | $\ge 6.0$ | Xuất khẩu Semantic Layer phục vụ tích hợp công cụ BI |
| **Frontend Framework** | **Next.js 14 (App Router)** | 14.2+ | React server/client components, tối ưu SEO và routing linh hoạt |
| **Frontend Styling** | **Tailwind CSS**, **Lucide React** | Standard | Thiết kế giao diện hiện đại, responsive, icon phong phú |
| **Code Viewer & Highlighting** | **PrismJS** | Standard | Highlight cú pháp SQL và YAML trên giao diện Web UI |
| **DevOps & Containers** | **Docker & Docker Compose** | Multi-stage | Đồng bộ môi trường Dev / Staging / Production |
| **Testing Framework** | **pytest, pytest-asyncio, httpx** | $\ge 8.0$ | Async unit & integration testing với mock LLM/DB |

---

## 5. Architectural Design Decisions

| Quyết định Kiến trúc | Lựa chọn Thực tế | Phương án Thay thế đã Xét | Lý do & Giá trị mang lại |
|---|---|---|---|
| **Query Engine Pattern** | **Deterministic Semantic Compilation** | Text-to-SQL tự do qua LLM | Đảm bảo tính chính xác 100%, không ảo giác, loại trừ rủi ro SQL Injection và lỗi cú pháp. |
| **Phạm vi Query Execution** | **CHỈ áp dụng Live DB** | Áp dụng cho cả SQL Dump | SQL Dump chỉ chứa DDL cấu trúc, không có môi trường chạy dữ liệu thực tế. |
| **Schema Enrichment** | **2-Pass Hierarchical + Clustering** | 1-Pass Flat Prompting | Tối ưu context window của LLM cho database lớn (> 20-50 bảng), đảm bảo từ vựng nghiệp vụ nhất quán trên toàn hệ thống. |
| **Bảo vệ Dữ liệu Live DB** | **sqlglot AST Inspection + Read-Only SELECT** | Phân quyền DB user thuần túy | Ngăn ngừa mọi hành vi sửa đổi dữ liệu ở cấp độ ứng dụng, tự động gán trần `LIMIT 100` và `timeout = 15s`. |
| **Lưu trữ Thông tin Nhạy cảm** | **Fernet Symmetric Encryption** | Lưu Plaintext / Hashing một chiều | Fernet cho phép giải mã 2 chiều an toàn trong bộ nhớ khi cần kết nối lại DB mà không để lộ connection string ra ngoài. |
| **Quản trị Chỉ số (Metrics)** | **MetricDefinition v2 + Version History** | Lưu chuỗi SQL tự do | Hỗ trợ quản trị công thức, kiểu tổng hợp (`SUM`, `COUNT`, `AVG`...), bộ lọc độc lập và truy vết lịch sử thay đổi phiên bản. |
| **Phân quyền Ứng dụng** | **Workspace-scoped RBAC** (`admin`, `data_lead`, `member`) | Vai trò toàn cục trên tài khoản | Một người có thể giữ vai trò khác nhau theo Workspace; JWT/profile không chứa vai trò ứng dụng toàn cục. |
| **Visual Dashboard Layout** | **Singleton chia sẻ + Optimistic Concurrency** | `localStorage` / nhiều dashboard theo user / last-write-wins | Một layout chung mỗi Semantic Database (key `db_id`), mọi vai trò Workspace có `can_query` đều sửa được; xung đột version hiển thị rõ và phục hồi được, không ghi đè thầm lặng. |

---

## 6. Database Schema — Metadata Store

Các bảng ORM được định nghĩa trong `src/models/db.py`. RBAC chỉ tồn tại trên membership của từng Workspace; bảng `users` không có cột role.

```mermaid
erDiagram
    users ||--o{ user_sessions : "has sessions (1-N)"
    users ||--o{ imported_schemas : "owns (1-N)"
    users ||--o{ live_target_databases : "owns (1-N)"
    users ||--o{ semantic_databases : "creates (1-N)"
    users ||--o{ semantic_metrics : "creates/approves (1-N)"
    users ||--o{ metric_versions : "changes (1-N)"
    users ||--o{ organization_members : "joins workspaces (1-N)"

    organizations ||--o{ organization_members : "has members (1-N)"
    organizations ||--o{ organization_invitations : "issues invites (1-N)"
    organizations ||--o{ semantic_databases : "owns semantic DBs (1-N)"

    semantic_databases ||--o{ semantic_tables : "contains (1-N)"
    semantic_databases ||--o{ semantic_metrics : "contains (1-N)"
    semantic_databases ||--o{ canonical_relationships : "contains (1-N)"
    semantic_databases ||--o| dashboard_layouts : "has singleton layout (1-1)"
    users ||--o| dashboard_layouts : "updated_by (0-1, SET NULL)"

    semantic_tables ||--o{ semantic_columns : "contains (1-N)"
    semantic_tables ||--o{ canonical_relationships : "joins from/to (1-N)"
    semantic_tables ||--o{ semantic_metrics : "base entity for (1-N)"

    semantic_metrics ||--o{ metric_versions : "tracks versions (1-N)"

    users {
        int id PK
        string email UK
        string username UK
        string hashed_password
        string full_name
        string status "active | inactive | suspended"
        datetime created_at
        datetime updated_at
    }

    organizations {
        int id PK
        string name
        string slug UK
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    organization_members {
        int id PK
        int org_id FK
        int user_id FK
        string role "admin | data_lead | member"
        datetime joined_at
        datetime updated_at
    }

    organization_invitations {
        int id PK
        int org_id FK
        int inviter_id FK
        string invitee_email
        string role "admin | data_lead | member"
        string token_hash UK
        datetime expires_at
        string status "pending | accepted | revoked | expired"
    }

    user_sessions {
        int id PK
        int user_id FK
        string refresh_token_hash UK
        string user_agent
        string ip_address
        datetime expires_at
        boolean revoked
        datetime created_at
    }

    imported_schemas {
        int id PK
        int created_by FK
        string display_name
        string dialect "postgresql | mysql | sqlite"
        json schema_metadata
        int semantic_db_id FK
        datetime created_at
        datetime updated_at
    }

    live_target_databases {
        int id PK
        int created_by FK
        string display_name
        string dialect "postgresql | mysql | sqlite"
        text conn_url_enc "Fernet ciphertext"
        json schema_metadata
        int semantic_db_id FK
        datetime created_at
        datetime updated_at
    }

    semantic_databases {
        int id PK
        int created_by FK
        string display_name
        string db_type "postgresql | mysql | sqlite"
        text conn_url_enc "Fernet ciphertext"
        string status "draft | active | archived"
        datetime created_at
        datetime updated_at
    }

    dashboard_layouts {
        int id PK
        int db_id FK "UK uq_dashboard_layouts_db_id (singleton per db)"
        json layout_json "Widget configs (chart, dimension, filters)"
        int version "default 1, optimistic concurrency"
        int updated_by FK "NULL on user delete (SET NULL)"
        datetime created_at
        datetime updated_at
    }

    semantic_tables {
        int id PK
        int db_id FK
        string table_name
        string business_name
        text description
        bigint row_count_approx
        string physical_schema
        string primary_key_column
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    semantic_columns {
        int id PK
        int table_id FK
        string column_name
        string data_type
        string business_name
        text description
        boolean is_primary_key
        boolean is_foreign_key
        string fk_target_table
        string fk_target_column
        boolean is_nullable
        boolean is_time_dimension
        json allowed_values
        datetime created_at
        datetime updated_at
    }

    semantic_metrics {
        int id PK
        int db_id FK
        int created_by FK
        string name
        text description
        text sql_template
        string source "ai | manual"
        string status "draft | pending_approval | needs_review | approved | unverified"
        int base_entity_id FK
        text formula
        string aggregation_type
        json definition
        int version
        int approved_by FK
        datetime created_at
        datetime updated_at
    }

    canonical_relationships {
        int id PK
        int connection_id FK
        int from_entity_id FK
        int to_entity_id FK
        string relationship_type "many_to_one | one_to_one"
        text join_condition
        string relationship_key UK
        string constraint_name
        json column_pairs
        string validation_status "valid | invalid"
        datetime created_at
    }

    metric_versions {
        int id PK
        int metric_id FK
        int version
        text formula
        json definition
        int changed_by FK
        text change_reason
        datetime created_at
    }
```

---

## 7. Security & Governance Principles

1. **Schema-Only Introspection:** Agent không bao giờ truy vấn dữ liệu nhạy cảm của khách hàng trong bước sinh Semantic Layer.
2. **Deterministic Query Compilation:** Không để LLM tự viết SQL lúc truy vấn dữ liệu thực tế nhằm loại bỏ hoàn toàn các rủi ro bảo mật và sai sót công thức.
3. **Double Guardrails on Execution:** Mọi câu truy vấn gửi tới Live DB đều được bọc kiểm tra AST với `sqlglot`, gán cứng trần `LIMIT 100` và `timeout = 15s`.
4. **Credential Isolation:** Toàn bộ chuỗi kết nối Target DB được mã hóa Fernet đối xứng trước khi ghi vào Database và chỉ giải mã trong RAM khi thực thi tác vụ.
5. **Workspace-scoped RBAC:** `admin` chỉ quản trị thành viên và invitation trong Workspace hiện tại, không phải quản trị viên toàn nền tảng. `data_lead` quản trị schema và metric; `member` chỉ gửi metric mới. Cả ba vai trò được xem catalog đã duyệt, query Live DB và dùng chat/data assistant.
6. **Last-admin Invariant:** Workspace luôn phải còn ít nhất một `admin`; mọi thao tác hạ vai trò hoặc xóa admin cuối cùng đều bị từ chối, kể cả tự hạ vai trò hoặc tự rời Workspace.
7. **Invitation Safety:** Chỉ Workspace Admin tạo/thu hồi URL mời. Link chứa vai trò `admin|data_lead|member`, token chỉ lưu dưới dạng hash, dùng một lần và hết hạn sau 7 ngày.
8. **Metric Review Boundary:** Submission của Member được server ép thành `unverified`, bất biến đối với Member, và trước khi duyệt chỉ hiển thị cho người tạo cùng Data Lead. Data Lead có thể sửa, xóa hoặc chuyển `unverified` thành `approved`; Admin chỉ xem catalog `approved`. Query compiler chỉ chấp nhận metric `approved`.
9. **Shared Dashboard Governance:** Dashboard là tài sản chung của Workspace, mọi vai trò có `can_query` đều được sửa (không phân biệt admin/data_lead/member). Truy vấn chỉ chạy trên Live DB đã duyệt (`query_supported`); SQL Dump không phát sinh query. Xung đột ghi đồng thời được phát hiện qua `expected_version` và trả `409 dashboard_version_conflict` với `current_version` để người dùng phục hồi, không ghi đè thầm lặng.
