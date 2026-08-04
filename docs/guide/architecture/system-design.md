---
title: "System Design"
description: "Tổng quan kiến trúc hệ thống P-069"
weight: 1
---

## System Architecture — P-069 AI Semantic Layer Agent

### Overview Diagram

```mermaid
graph TB
    subgraph Client["Client Layer"]
        UI["Next.js Frontend"]
    end

    subgraph API["API Layer — FastAPI"]
        AUTH["Auth: /api/v1/auth/*"]
        SEM["Semantic: /api/v1/semantic/*"]
    end

    subgraph Flow1["Flow 1 — Generate Pipeline"]
        G1["Introspect Node\nSQLAlchemy Inspector"]
        G2["Enrich Node\nLLM: business_name + description"]
        G3["Metric Suggest Node\nLLM: Business Metrics"]
        HITL["Review Node\nHITL Interrupt"]
        G4["Save Node\nPersist to Metadata Store"]
        G1 --> G2 --> G3 --> HITL --> G4
    end

    subgraph Data["Data Layer"]
        TARGET["Target DB\n(Postgres/MySQL/SQLite)\nSchema only — no data read"]
        METADB["Metadata Store\nPostgreSQL"]
    end

    UI --> AUTH --> Flow1
    UI --> SEM --> Flow1
    G1 -->|"Inspector API"| TARGET
    G4 -->|save| METADB
```

## Components

### 1. Frontend (Next.js)

- **Purpose:** HITL review UI cho BA/DA
- **Key Features:** Inline edit business_name, metric review, export
- **State Management:** React Context (AuthContext)

### 2. Backend (FastAPI)

- **Purpose:** API server xử lý auth + semantic layer pipeline
- **API Design:** RESTful endpoints (`/api/v1/auth/*`, `/api/v1/semantic/*`)
- **Auth:** JWT + Google OAuth

### 3. AI Agent (LangGraph)

- **Agent Type:** Linear pipeline with HITL interrupt
- **State:** `AgentState` TypedDict (`src/agents/state.py`)
- **Nodes:** introspect → enrich → metric_suggest → save
- **Tools:** SQLAlchemy Inspector (schema-only, no data query)

### 4. Database

- **Target DB:** PostgreSQL / MySQL / SQLite (read schema only via Inspector)
- **Metadata Store:** PostgreSQL (ORM via SQLAlchemy, migrations via Alembic)
- **Encryption:** Fernet for connection URLs

### 5. LLM

- **Model:** GPT-4o-mini via `get_llm()` factory (`src/services/llm.py`)
- **Temperature:** 0.0 (deterministic)
- **Usage:** business_name enrichment + metric suggestion

## Data Flow

1. User gửi `POST /api/v1/semantic/generate` với `db_id`
2. Introspect Node đọc schema metadata qua SQLAlchemy Inspector
3. Enrich Node gọi LLM sinh business_name + description (batch 5 bảng)
4. Metric Suggest Node gọi LLM đề xuất Business Metrics
5. HITL interrupt — BA/DA review & approve qua UI
6. Save Node persist vào Metadata Store
7. Export Service xuất JSON/YAML

## Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Framework | FastAPI | Async, auto-docs, type-safe |
| Agent | LangGraph | StateGraph + HITL Interrupt |
| DB Access | SQLAlchemy Inspector | Schema-only, no data read risk |
| LLM | GPT-4o-mini, T=0.0 | Cost-efficient, deterministic |
| Credential Storage | Fernet encryption | Reversible, symmetric key |
