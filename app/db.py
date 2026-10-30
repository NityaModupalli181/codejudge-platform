import os
import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "postgresql://judge:local-dev-change-me@localhost:5432/judge")

def connect():
    return psycopg.connect(DB, row_factory=dict_row)

def initialize():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
          id TEXT PRIMARY KEY, language TEXT NOT NULL, source TEXT NOT NULL,
          stdin TEXT NOT NULL DEFAULT '', expected TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL, result JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          finished_at TIMESTAMPTZ
        )
        """)
