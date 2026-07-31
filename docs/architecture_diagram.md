# Architecture Diagram — AI Semantic Layer Agent

## System Overview

```mermaid
graph TB
    User(["👤 User"]) --> UI["🖥️ React / Next.js UI"]
    UI -->|"REST API"| API["🌐 FastAPI Backend"]

    API --> GEN["⚙️ Flow 1: Generate Pipeline\nPOST /api/v1/semantic/generate"]
    API --> QRY["🔍 Flow 2: Query Pipeline\nPOST /api/v1/query"]

    GEN --> G1["Introspect Node\nSQLAlchemy Inspector"]
    G1 --> G2["Enrich Node\nGPT-4o-mini: business names"]
    G2 --> G3["Metric Suggest Node\nGPT-4o-mini: metrics"]
    G3 --> G4["Save Node\nMetadata Store"]

    QRY --> Q1["Schema Agent\nLLM chọn bảng"]
    Q1 --> Q2["SQL Gen Agent\nLLM viết SQL"]
    Q2 --> Q3["Validate Agent\nsqlparse: SELECT only"]
    Q3 --> Q4["Execute Agent\nread-only"]
    Q4 --> Q5["Format Agent\ntext/table/number"]

    G1 -->|introspect| DB[("🗄️ Target Database\nPostgreSQL / MySQL / SQLite")]
    G4 -->|save| META[("📐 Metadata Store\nSQLite dev / PostgreSQL prod")]
    Q1 -->|read| META
    Q4 -->|execute SQL| DB
```

---

## Flow 1 — Generate Pipeline

```mermaid
flowchart LR
    IN(["DB Connection URL"]) --> A
    A["Introspect\nSQLAlchemy"] --> B
    B["Enrich\nLLM batch"] --> C
    C["Metric Suggest\nLLM"] --> D
    D["Save\nMetadata Store"] --> OUT(["✅ Semantic Layer JSON"])
```

---

## Flow 2 — Query Pipeline

```mermaid
flowchart LR
    IN(["Câu hỏi + db_id"]) --> A
    A["Schema Agent\nChọn bảng"] --> B
    B["SQL Gen Agent\nViết SQL"] --> C
    C{"Validate\nsqlparse"}
    C -->|"✅ SELECT"| D["Execute\nread-only"]
    C -->|"❌ unsafe"| B
    D --> E["Format\ntext/table/number"]
    E --> OUT(["✅ Answer + SQL + Data"])
```

---

## Component Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI + Uvicorn | Async REST API |
| Flow 1 Agent | LangGraph StateGraph | Generate Semantic Layer |
| Flow 2 Agent | LangGraph Multi-Agent | NL2SQL query |
| LLM | GPT-4o-mini | Enrich + SQL generation |
| DB Abstraction | SQLAlchemy | Introspection + execution |
| SQL Safety | sqlparse | Whitelist SELECT only |
| Metadata Store | SQLite (dev) / PostgreSQL (prod) | Semantic definitions |
| Target DB | PostgreSQL / MySQL / SQLite | DB người dùng query |
