# Worklog — AI Semantic Layer Agent (P-069)

> Lịch sử công việc và các mốc phát triển dự án VinUni AI20K Build Phase (Cohort 3).

---

## 2026-08-01: Khởi động Dự án & Thiết kế Kiến trúc
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Team | Họp định hướng bài toán & phân tích yêu cầu PRD/BRIEF | ✅ Done | [PRD.md](file:///d:/project/P-069/docs/PRD.md), [BRIEF.md](file:///d:/project/P-069/docs/BRIEF.md) | 4h |
| Lead Dev | Thiết kế kiến trúc hệ thống 2 luồng và ERD 10 bảng | ✅ Done | [ARCHITECTURE.md](file:///d:/project/P-069/ARCHITECTURE.md), [DATABASE_DESIGN.md](file:///d:/project/P-069/docs/DATABASE_DESIGN.md) | 5h |
| Dev | Khởi tạo repo, pre-commit hooks, cấu hình Alembic & FastAPI | ✅ Done | Initial repo structure, alembic migrations | 3h |

**Tổng kết ngày:** Thống nhất kiến trúc 2 luồng cốt lõi (Flow 1 & Flow 2) và thiết kế ERD Metadata Store.

---

## 2026-08-05: Ingestion Engine & DDL Dump Parser
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Dev 1 | Xây dựng `SQLAlchemy Inspector` đọc schema Live DB | ✅ Done | `src/services/introspection.py` | 4h |
| Dev 2 | Xây dựng `SqlDumpScanner & Parser` phân tích DDL đa dialect | ✅ Done | `src/services/sql_dump_scanner.py`, `sql_dump_parser.py` | 5h |
| QA | Viết unit tests cho dump parser và introspection engine | ✅ Done | `tests/test_services/test_sql_dump_parser.py` | 3h |

**Tổng kết ngày:** Hoàn thành module tiếp nhận schema từ cả 2 nguồn (Live Database và SQL Dump DDL).

---

## 2026-08-09: 2-Pass AI Semantic Enrichment & LangGraph Flow 1
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Lead Dev | Xây dựng Pass 1 Global Domain Glossary & Graph Clustering | ✅ Done | `src/services/pass1_global_glossary.py`, `clustering.py` | 5h |
| Dev 1 | Xây dựng Pass 2 Cluster Enrichment & Fallback Generator | ✅ Done | `src/services/pass2_cluster_enrichment.py` | 4.5h |
| Dev 2 | Xây dựng LangGraph StateGraph Flow 1 và HITL Interrupt Node | ✅ Done | `src/agents/graph.py`, `src/agents/nodes/` | 4h |

**Tổng kết ngày:** Hoàn thành luồng AI tự động sinh tên nghiệp vụ tiếng Việt và mô tả chi tiết cho bảng/cột theo cụm.

---

## 2026-08-12: Deterministic Semantic Query Engine & AST Guardrails (Flow 2)
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Lead Dev | Xây dựng `SemanticQueryCompiler` và Graph Join Resolver | ✅ Done | `src/services/query_compiler.py` | 6h |
| Dev 1 | Tích hợp `sqlglot` AST Guardrails (chặn lệnh ghi, inject LIMIT 100) | ✅ Done | AST verification logic & timeout enforcement | 4h |
| Dev 2 | Xây dựng `query_execution.py` thực thi Read-Only trên Live DB | ✅ Done | `src/services/query_execution.py` | 3.5h |

**Tổng kết ngày:** Hoàn thành động cơ biên dịch truy vấn xác định chuẩn xác 100%, loại trừ hoàn toàn ảo giác.

---

## 2026-08-14: Multi-Agent Conversational Router & Query Clarifier Wizard
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Dev 1 | Xây dựng Chat Orchestrator Graph (`chitchat` vs `metric_suggest`) | ✅ Done | `src/agents/chat_graph.py` | 4h |
| Dev 2 | Xây dựng Query Clarifier Wizard Graph hỏi đáp làm rõ từng bước | ✅ Done | `src/agents/query_clarifier/graph.py` | 5h |
| QA | Viết tests cho multi-agent routes và wizard flows | ✅ Done | `tests/test_agents/`, `tests/test_api/` | 3h |

**Tổng kết ngày:** Tích hợp trợ lý hội thoại AI đa tác tử hỗ trợ người dùng xây dựng câu truy vấn nhanh chóng.

---

## 2026-08-16: Next.js Frontend UI, Test Suite & Evaluation Evidences
| Member | Task | Status | Output | Time |
|---|---|---|---|:---:|
| Frontend Dev | Hoàn thiện 5 Views Next.js 14 Web UI & Modal Wizard | ✅ Done | `frontend/src/app/`, `frontend/src/components/` | 6h |
| Lead Dev | Chạy toàn bộ Test Suite (621 passed) và kiểm tra Ruff linter | ✅ Done | 621 tests passing, 0 linter errors | 2h |
| Team | Soạn thảo Báo cáo Đánh giá Thực nghiệm 6 Test Cases | ✅ Done | [report.md](file:///d:/project/P-069/eval/results/report.md) | 3h |

**Tổng kết ngày:** Toàn bộ deliverables cho Demo Day đã hoàn tất 100% và sẵn sàng báo cáo.
