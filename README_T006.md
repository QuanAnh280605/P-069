# [T006] Import SQL Dump và trả về Schema Metadata

## TL;DR

Cho phép tải file PostgreSQL/MySQL `.sql`, parse DDL thành technical schema metadata, hiển thị preview và lưu lại theo tên gợi nhớ. Hệ thống không thực thi SQL, không đọc row data và không gọi LLM.

## Chuẩn bị môi trường

Yêu cầu: Python 3.11, Node.js, npm và Docker Desktop.

Tại thư mục gốc:

```bash
cp .env.example .env
python -m venv .venv
source .venv/Scripts/activate  # Git Bash
python -m pip install -r requirements.txt
```

PowerShell dùng lệnh kích hoạt sau:

```powershell
.\.venv\Scripts\Activate.ps1
```

Tạo `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Hướng dẫn chạy

### Data và Backend

Các lệnh dưới đây chạy được trong Git Bash lẫn PowerShell khi virtual environment đã active:

```bash
docker compose -f docker-compose.dev.yml up postgres pgweb -d
python -m alembic upgrade head
python -m uvicorn src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000
```

Không dùng đường dẫn Windows như `.\.venv\Scripts\uvicorn.exe` trong Git Bash vì ký tự `\` bị shell xử lý. Swagger: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Mở `http://localhost:3000` và đăng nhập.

## What's New / Changelog

| Tên file | Nội dung chính |
|---|---|
| `src/models/schema_metadata.py` | Contract metadata cho schema, table, column, PK/FK và diagnostic. |
| `src/services/sql_dump_scanner*.py` | Đọc file có giới hạn, nhận diện dialect và loại row data. |
| `src/services/sql_dump_parser*.py` | Parse DDL PostgreSQL/MySQL bằng SQLGlot thành canonical metadata. |
| `src/services/schema_ingestion.py` | Điều phối scanner → parser → response. |
| `src/models/db.py`, `alembic/versions/d87dc6a5afe1_*.py` | Bảng `imported_schemas` và migration lưu metadata theo user. |
| `src/services/imported_schema_service.py` | Lưu, liệt kê, mở lại và xóa imported schema. |
| `src/api/routes.py` | API preview và CRUD saved schema. |
| `frontend/src/components/SqlDump*.tsx` | Form upload, tên gợi nhớ, nút lưu và technical preview. |
| `frontend/src/components/ImportedSchemaList.tsx` | Bảng danh sách schema đã lưu, mở preview và xóa. |
| `frontend/src/lib/api.ts` | Kiểu dữ liệu và API client cho upload/saved schemas. |
| `tests/fixtures/sql_dumps/`, `tests/test_*` | Fixtures và regression tests cho scanner/parser/API. |
| `requirements.txt` | Thêm `sqlglot`. |

## Kết quả trực quan

Trong card Import SQL Dump, ô **Tên gợi nhớ** nằm trên hàng chọn file/dialect. Khi lưu thành công, preview tự đóng. Component **Danh sách schema đã lưu** được tách riêng và đặt sau card kết nối database; danh sách cho phép mở lại hoặc xóa schema. Các diagnostic `UNSUPPORTED_STATEMENT` vẫn được giữ trong API nhưng không hiển thị trên UI.

## How to Test

### Kiểm tra nhanh

1. Chạy Data, Backend và Frontend theo hướng dẫn trên.
2. Mở dashboard và đăng nhập.
3. Chọn `tests/fixtures/sql_dumps/postgresql_schema.sql`.
4. Giữ **Auto detect**, bấm **Upload & Preview**.
5. Nhập tên gợi nhớ, bấm **Lưu schema** và kiểm tra bản ghi xuất hiện trong danh sách.
6. Bấm **Mở preview** để tải lại metadata đã lưu; bấm biểu tượng thùng rác để xóa.

### Kịch bản chính

| Kịch bản | Kết quả mong đợi |
|---|---|
| `postgresql_schema.sql`, auto | Parse thành công, dialect PostgreSQL. |
| `mysql_schema.sql`, auto | Parse thành công, dialect MySQL. |
| `postgresql_dump_schema.sql`, chọn PostgreSQL | Có preview đúng table/column/PK/FK; warning ngoài phạm vi không hiển thị trên UI. |
| `test_schema_dump.sql`, auto | HTTP 422 `DIALECT_AMBIGUOUS` vì file trộn dấu hiệu nhiều dialect. |
| `test_schema_dump.sql`, chọn dialect | Có thể preview phần DDL tương thích; phần không biểu diễn được tạo warning. |
| File có `INSERT` | Row payload bị bỏ qua và không xuất hiện trong response. |
| Chỉ upload/preview | Không tạo bản ghi mới. |
| Bấm Lưu schema | Tạo bản ghi `imported_schemas` thuộc user hiện tại. |
| User khác mở/xóa schema | Trả HTTP 404. |

### Automated checks

```bash
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
cd frontend
npm run lint
npm run build
```

## Giới hạn

- Chỉ hỗ trợ PostgreSQL và MySQL trong phạm vi DDL đã kiểm thử.
- Index, sequence object, UNIQUE/CHECK và FK actions chưa được canonical metadata biểu diễn đầy đủ nên có thể tạo warning.
- Chỉ technical metadata được lưu; không có draft approval, LLM enrichment, HITL hoặc semantic metrics.
