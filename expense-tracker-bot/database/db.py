from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path
import aiosqlite
from config.settings import settings

@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager quản lý kết nối tới SQLite database."""
    # Tự động tạo thư mục chứa database nếu chưa tồn tại
    db_file = Path(settings.db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn

async def init_db() -> None:
    """Khởi tạo cấu trúc các bảng trong cơ sở dữ liệu."""
    async with get_connection() as conn:
        # 1. Bảng users
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                currency TEXT DEFAULT 'VND',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Bảng transactions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('expense', 'income')),
                category TEXT NOT NULL,
                note TEXT,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Tạo index tăng tốc độ query thống kê
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_user_date 
            ON transactions(user_id, transaction_date)
        """)

        # 3. Bảng budgets
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                monthly_limit INTEGER NOT NULL,
                UNIQUE(user_id, category),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await conn.commit()
