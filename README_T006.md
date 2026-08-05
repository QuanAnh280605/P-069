# [T006] Import SQL Dump và xem trước Technical Schema

## 1. TL;DR

Task T006 bổ sung luồng tải lên PostgreSQL/MySQL schema dump, parse DDL an toàn mà không thực thi SQL và hiển thị technical schema preview. Preview hiện chỉ lưu trong RAM, chưa chạy LLM/HITL Save Node và chưa ghi vào Metadata Store.

## 2. Chuẩn bị môi trường

### Yêu cầu

- Python 3.11.
- Node.js/npm tương thích Next.js 16.
- Docker Desktop và Docker Compose.
- Các port `3000`, `5432`, `8000`, `8081` đang trống.

### Cấu hình backend

Tại thư mục gốc repository:

```powershell
Copy-Item .env.example .env
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sinh Fernet key:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Cập nhật `.env`:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev
ENCRYPTION_KEY=<fernet-key-vừa-sinh>
SQL_DUMP_PREVIEW_ENABLED=true
CORS_ORIGINS=http://localhost:3000
```

Preview không gọi LLM nên không cần OpenAI API để test luồng này.

### Cấu hình frontend

Tạo `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 3. Hướng dẫn chạy hệ thống

### Data — PostgreSQL Metadata Store

```powershell
docker compose -f docker-compose.dev.yml up postgres pgweb -d
.\.venv\Scripts\alembic.exe upgrade head
```

- PostgreSQL: `localhost:5432`.
- PgWeb: `http://localhost:8081`.
- T006 không thay đổi ORM/database schema nên không có migration mới.

### Backend

```powershell
.\.venv\Scripts\uvicorn.exe src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000
```

- Health check: `http://localhost:8000/health`.
- Swagger: `http://localhost:8000/docs`.

Hoặc chạy backend bằng Docker:

```powershell
docker compose -f docker-compose.dev.yml up postgres backend pgweb --build
```

Không chạy đồng thời backend local và Docker trên port `8000`.

### Frontend

Mở terminal khác:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Truy cập `http://localhost:3000`.

## 4. What's New / Changelog

| Tên file | Nội dung chính |
|---|---|
| `src/models/schema_metadata.py` | Canonical models cho schema, table, column, PK/FK, diagnostics và completeness. |
| `src/models/schemas.py` | Response models cho preview và approval. |
| `src/agents/state.py` | Typed raw schema, source mode, dialect và parse diagnostics. |
| `src/config.py` | Giới hạn file/statement, feature flag, TTL và draft capacity. |
| `src/services/sql_dump_scanner_models.py` | Models và limits cho scanner. |
| `src/services/sql_dump_scanner.py` | Đọc bounded chunks, nhận diện dialect, loại row data và giữ core DDL. |
| `src/services/sql_dump_parser_models.py` | Internal builders và safe parser errors. |
| `src/services/sql_dump_parser.py` | Parse table/column/default/PK/FK; hỗ trợ ALTER constraints và column defaults. |
| `src/services/schema_ingestion.py` | Orchestrate scanner → parser → preview draft. |
| `src/services/preview_draft_store.py` | In-memory owner-bound drafts với TTL và capacity. |
| `src/api/routes.py` | Upload/get/approve preview APIs và structured error mapping. |
| `frontend/src/components/SqlDumpPreviewUploader.tsx` | Form chọn file, dialect, upload và error/loading states. |
| `frontend/src/app/page.tsx` | Gắn Import SQL Dump card vào dashboard. |
| `frontend/src/lib/api.ts` | Types, API client và format diagnostic location. |
| `frontend/src/app/semantic/drafts/[draft_id]/review/page.tsx` | Trang technical schema review. |
| `requirements.txt` | Pin `sqlglot==30.13.0`. |
| `tests/fixtures/sql_dumps/` | PostgreSQL/MySQL golden dumps và các fixture regression. |
| `tests/test_models/test_schema_metadata.py` | Test canonical metadata invariants. |
| `tests/test_services/test_sql_dump_*.py` | Test scanner, parser, fixtures và SQLGlot compatibility. |
| `tests/test_services/test_preview_draft_store.py` | Test TTL, capacity và owner isolation. |
| `tests/test_api/test_import_dump_preview.py` | Test preview API, authentication và no-persistence boundary. |

## 5. Kết quả trực quan

### Dashboard

Card **Import SQL Dump — Experimental Preview** có:

- File picker `.sql` và giới hạn client 20 MiB.
- Chọn `Tự nhận diện`, `PostgreSQL` hoặc `MySQL`.
- Nút **Upload & Preview** cùng loading state.
- Banner đỏ cho fatal errors.
- Ghi chú draft chỉ nằm trong RAM.

### Review page

Route: `/semantic/drafts/{draft_id}/review`.

- Hiển thị dialect, `RAM ONLY` và thời gian hết hạn.
- Hiển thị diagnostics kèm code, dòng và cột.
- Hiển thị schema-qualified tables, columns, types, nullability và PK/FK count.
- Nút **Phê duyệt preview** chỉ đổi trạng thái trong RAM, không gọi Save Node.

## 6. How to Test

### Kiểm tra nhanh

1. Chạy Data, Backend và Frontend theo mục 3.
2. Mở `http://localhost:3000` và đăng nhập.
3. Chọn `tests/fixtures/sql_dumps/postgresql_schema.sql`.
4. Giữ **Tự nhận diện**, bấm **Upload & Preview**.
5. Xác nhận chuyển tới `/semantic/drafts/{draft_id}/review`.
6. Kiểm tra dialect, tables, columns, PK/FK và diagnostics.
7. Bấm **Phê duyệt preview** và xác nhận nút đổi trạng thái.

### Các kịch bản chính

| Kịch bản | File/thao tác | Kết quả mong đợi |
|---|---|---|
| PostgreSQL auto-detect | `postgresql_schema.sql` | Preview thành công, dialect PostgreSQL. |
| PostgreSQL owner/sequence | `postgresql_dump_schema.sql` | Không còn lỗi `unsupported AST`; sequence defaults được giữ. |
| MySQL auto-detect | `mysql_schema.sql` | Preview thành công, dialect MySQL. |
| Ambiguous dialect | `test_schema_dump.sql`, để auto | Trả `DIALECT_AMBIGUOUS`. |
| Explicit dialect | `test_schema_dump.sql`, chọn dialect | Có preview; có thể kèm warning non-core/FK actions. |
| Owner isolation | User B mở draft của User A | Trả `Preview draft not found or expired`. |
| Restart backend | Mở lại draft sau restart | Draft không còn vì store chỉ nằm trong RAM. |
| No persistence | Approve rồi kiểm tra Metadata Store | Không có semantic records mới. |

`test_schema_dump.sql` trộn `SERIAL` và `AUTO_INCREMENT`; explicit override chỉ chọn parser dialect, không chứng nhận file chạy được trên database thật.

## 7. Automated Tests

### Regression tests T006

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models/test_schema_metadata.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_services/test_sql_dump_scanner.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_services/test_sql_dump_parser.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_services/test_preview_draft_store.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_api/test_import_dump_preview.py -q
```

### Full backend checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\ruff.exe format --check src tests
```

Kết quả tham chiếu: `134 tests passed`, Ruff check/format passed.

### Frontend checks

```powershell
Set-Location frontend
npm run lint
npm run build
```

Kết quả tham chiếu: ESLint không có error; Next.js production build passed.

## 8. Giới hạn hiện tại

- Chỉ hỗ trợ PostgreSQL/MySQL trong phạm vi fixtures đã kiểm thử.
- Index, sequence objects, UNIQUE/CHECK và FK actions chưa được canonical IR biểu diễn đầy đủ.
- Draft chỉ nằm trong RAM của một backend process và bị tắt trong production.
- Chưa có multipart production endpoint.
- Chưa có Enrich/Metric nodes, HITL checkpoint hoặc persistence chính thức.
