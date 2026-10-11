from datetime import date
from typing import List, Dict, Any, Optional
from database.db import get_connection

async def register_user(user_id: int, username: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật thông tin user."""
    async with get_connection() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
        """, (user_id, username))
        await conn.commit()

async def add_transaction(
    user_id: int,
    amount: int,
    trans_type: str,
    category: str,
    note: Optional[str] = None
) -> int:
    """Thêm một giao dịch mới và trả về ID."""
    async with get_connection() as conn:
        cursor = await conn.execute("""
            INSERT INTO transactions (user_id, amount, type, category, note)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, trans_type, category, note))
        await conn.commit()
        return cursor.lastrowid

async def delete_transaction(transaction_id: int, user_id: int) -> bool:
    """Xóa một giao dịch (dùng cho chức năng Hủy)."""
    async with get_connection() as conn:
        cursor = await conn.execute("""
            DELETE FROM transactions
            WHERE id = ? AND user_id = ?
        """, (transaction_id, user_id))
        await conn.commit()
        return cursor.rowcount > 0

async def update_transaction_category(
    transaction_id: int,
    user_id: int,
    new_category: str
) -> bool:
    """Cập nhật danh mục cho một giao dịch."""
    async with get_connection() as conn:
        cursor = await conn.execute("""
            UPDATE transactions
            SET category = ?
            WHERE id = ? AND user_id = ?
        """, (new_category, transaction_id, user_id))
        await conn.commit()
        return cursor.rowcount > 0

async def get_transaction(transaction_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin 1 giao dịch."""
    async with get_connection() as conn:
        async with conn.execute("""
            SELECT id, user_id, amount, type, category, note, transaction_date
            FROM transactions
            WHERE id = ? AND user_id = ?
        """, (transaction_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_daily_expense(user_id: int, target_date: Optional[date] = None) -> int:
    """Tính tổng chi tiêu trong 1 ngày."""
    if target_date is None:
        target_date = date.today()
    date_str = target_date.strftime("%Y-%m-%d")

    async with get_connection() as conn:
        async with conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE user_id = ? 
              AND type = 'expense'
              AND date(transaction_date) = date(?)
        """, (user_id, date_str)) as cursor:
            row = await cursor.fetchone()
            return row["total"] if row else 0

async def get_period_summary(
    user_id: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Lấy báo cáo tổng hợp: Tổng thu, tổng chi và phân bổ theo danh mục chi tiêu.
    start_date, end_date dạng 'YYYY-MM-DD'
    """
    async with get_connection() as conn:
        # Tổng chi
        async with conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_expense
            FROM transactions
            WHERE user_id = ? 
              AND type = 'expense'
              AND date(transaction_date) BETWEEN date(?) AND date(?)
        """, (user_id, start_date, end_date)) as cursor:
            row = await cursor.fetchone()
            total_expense = row["total_expense"] if row else 0

        # Tổng thu
        async with conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_income
            FROM transactions
            WHERE user_id = ? 
              AND type = 'income'
              AND date(transaction_date) BETWEEN date(?) AND date(?)
        """, (user_id, start_date, end_date)) as cursor:
            row = await cursor.fetchone()
            total_income = row["total_income"] if row else 0

        # Chi tiết theo từng danh mục chi tiêu
        async with conn.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = ? 
              AND type = 'expense'
              AND date(transaction_date) BETWEEN date(?) AND date(?)
            GROUP BY category
            ORDER BY total DESC
        """, (user_id, start_date, end_date)) as cursor:
            rows = await cursor.fetchall()
            categories = {row["category"]: row["total"] for row in rows}

        return {
            "total_expense": total_expense,
            "total_income": total_income,
            "net": total_income - total_expense,
            "categories": categories
        }

async def get_all_transactions(user_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
    """Lấy danh sách các giao dịch để phục vụ xuất Excel."""
    async with get_connection() as conn:
        async with conn.execute("""
            SELECT id, transaction_date, type, amount, category, note
            FROM transactions
            WHERE user_id = ?
            ORDER BY transaction_date DESC
            LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def set_budget(user_id: int, category: str, monthly_limit: int) -> None:
    """Đặt hoặc cập nhật ngân sách cho một danh mục."""
    async with get_connection() as conn:
        await conn.execute("""
            INSERT INTO budgets (user_id, category, monthly_limit)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit
        """, (user_id, category, monthly_limit))
        await conn.commit()

async def get_budget_status(user_id: int, category: str) -> Optional[Dict[str, Any]]:
    """Kiểm tra tình trạng ngân sách của danh mục trong tháng hiện tại."""
    first_day_of_month = date.today().replace(day=1).strftime("%Y-%m-%d")

    async with get_connection() as conn:
        # Lấy hạn mức
        async with conn.execute("""
            SELECT monthly_limit FROM budgets
            WHERE user_id = ? AND category = ?
        """, (user_id, category)) as cursor:
            b_row = await cursor.fetchone()
            if not b_row:
                return None
            monthly_limit = b_row["monthly_limit"]

        # Lấy số tiền đã chi trong tháng
        async with conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as spent
            FROM transactions
            WHERE user_id = ? 
              AND category = ?
              AND type = 'expense'
              AND date(transaction_date) >= date(?)
        """, (user_id, category, first_day_of_month)) as cursor:
            s_row = await cursor.fetchone()
            spent = s_row["spent"] if s_row else 0

        percent = (spent / monthly_limit) * 100 if monthly_limit > 0 else 0
        return {
            "monthly_limit": monthly_limit,
            "spent": spent,
            "percent": percent,
            "remaining": monthly_limit - spent
        }

async def get_all_active_user_ids() -> List[int]:
    """Lấy danh sách user IDs để gửi thông báo nhắc nhở."""
    async with get_connection() as conn:
        async with conn.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row["user_id"] for row in rows]
