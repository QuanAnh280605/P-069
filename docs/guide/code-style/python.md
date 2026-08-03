---
title: "Python & FastAPI Code Style"
description: "Chuẩn code Python & FastAPI cho dự án AI Semantic Layer"
weight: 1
---

## Python & FastAPI Style Guide

Tài liệu này định nghĩa chuẩn mực viết code Python, FastAPI, Pydantic v2 và SQLAlchemy Async cho dự án.

---

### 1. Architecture & Domain Separation

Cấu trúc dự án tuân theo mô hình phân tầng Domain-Driven Modularity:

* **`src/api/`**: Chứa FastAPI routes & endpoint controllers. Chỉ nhận request, validate qua Pydantic DTO, gọi Service/Agent và trả về Response.
* **`src/services/`**: Chứa business logic, LLM wrappers, Export logic.
* **`src/agents/`**: Chứa các LangGraph nodes & workflow state transitions.
* **`src/models/`**: Chứa Database ORM models (SQLAlchemy) và Pydantic Schemas.

---

### 2. Type Hints — BẮT BUỘC

```python
# ✅ TỐT — Full type hints
async def analyze_schema(target_db_id: str) -> dict[str, Any]:
    """Phân tích schema metadata của Target DB."""
    result = await inspector_service.get_tables(target_db_id)
    return {"tables": result}

# ❌ TỆ — Không type hints
def process(data):
    x = model.run(data)
    return x
```

---

### 3. Pydantic v2 Best Practices

1. **Phân tách Request & Response Schemas**:
   Không sử dụng chung 1 model cho cả Create, Update và Response để tránh rò rỉ dữ liệu nhạy cảm (ví dụ: password hash, encrypted URL).
   * `UserCreate`: Nhận email, password, full_name.
   * `UserResponse`: Trả về id, email, full_name, role, created_at.
2. **Model Config cho SQLAlchemy ORM**:
   Sử dụng `ConfigDict(from_attributes=True)` trong Pydantic v2 để convert từ SQLAlchemy ORM object sang Pydantic DTO:
   ```python
   from pydantic import BaseModel, ConfigDict

   class UserResponse(BaseModel):
       id: str
       email: str
       role: str

       model_config = ConfigDict(from_attributes=True)
   ```

---

### 4. Async & Non-blocking I/O

* **Luôn dùng `async def`**: Mọi I/O operation (Database queries qua SQLAlchemy `AsyncSession`, HTTP calls qua `httpx`, LLM invocation qua LangChain async methods `ainvoke`) bắt buộc dùng `async def` và `await`.
* **Không dùng thư viện blocking trong `async def`**: Không dùng `requests` synchronous, `time.sleep()`, hay DB driver đồng bộ. Nếu phải dùng thư viện CPU-bound hoặc sync library, cần chạy thông qua `run_in_executor`.

---

### 5. Function Rules & Constraints

- **Max 30 lines** per function — dài hơn $\rightarrow$ bắt buộc tách sub-functions.
- **Max 3 parameters** per function — nhiều hơn $\rightarrow$ đóng gói thành Pydantic Schema.
- **Luôn có return type hint** cho tất cả các hàm.
- **Docstring** tiếng Anh ngắn gọn cho các public functions.

---

### 6. Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| File | snake_case | `schema_inspector.py` |
| Function / Method | snake_case | `def extract_columns()` |
| Class / Model | PascalCase | `class SemanticTable` |
| Constant | UPPER_SNAKE | `FERNET_KEY_PREFIX = "gAAAA"` |

---

### 7. Import Order

```python
# 1. Standard library
import os
from typing import Any, Optional, List

# 2. Third-party packages
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local application modules
from src.config import get_settings
from src.models.db import User
```

---

### 8. Error Handling & Security

```python
# ✅ TỐT — Catch exception cụ thể & dùng FastAPI HTTPException
try:
    result = await llm_service.enrich_schema(prompt)
except OpenAIError as e:
    logger.error(f"LLM enrichment failed: {e}")
    raise HTTPException(status_code=502, detail="LLM service error")

# ❌ TỆ — Bare except (che lấp lỗi gốc)
try:
    result = await llm.ainvoke(prompt)
except:
    pass
```

* **Data Safety Constraint**: Không bao giờ thực thi truy vấn `SELECT` dữ liệu trên Target DB (chỉ dùng `SQLAlchemy Inspector` để đọc metadata).
* **Credential Protection**: Chuỗi kết nối Database `conn_url` luôn được mã hóa Fernet trước khi lưu vào DB.

---

### 9. Code Quality & Linting

Dự án sử dụng **Ruff** để tự động lint và format code:

```bash
# Check lỗi linting
ruff check src/ tests/

# Tự động sửa lỗi (auto-fix) & format
ruff check --fix src/ tests/
ruff format src/ tests/
```
