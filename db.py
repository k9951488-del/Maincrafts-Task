import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def add_expense(amount: float, category: str, description: str, date: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO expenses (amount, category, description, date, created_at) VALUES (?, ?, ?, ?, ?)",
            (amount, category.strip().title(), description.strip(), date, datetime.now().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid


def list_expenses(
    category: Optional[str] = None,
    month: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM expenses WHERE 1=1"
    params: list = []

    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)

    if month:
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month)

    query += " ORDER BY date DESC, created_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def delete_expense(expense_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_summary(month: Optional[str] = None) -> list[sqlite3.Row]:
    query = "SELECT category, SUM(amount) as total, COUNT(*) as count FROM expenses WHERE 1=1"
    params: list = []

    if month:
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month)

    query += " GROUP BY category ORDER BY total DESC"

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_total(month: Optional[str] = None) -> float:
    query = "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE 1=1"
    params: list = []

    if month:
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month)

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["total"]


def list_categories() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM expenses ORDER BY category"
        ).fetchall()
        return [row["category"] for row in rows]


def get_expense(expense_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
