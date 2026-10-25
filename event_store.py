"""
event_store.py - lớp lưu sự kiện dùng chung cho các honeypot và API.

Honeypot (ssh_honeypot.py, web_honeypot.py) GHI sự kiện bằng log_event().
API (api.py) ĐỌC sự kiện bằng query().
Hai bên chỉ giao tiếp qua file SQLite, nên chạy thành 2 tiến trình riêng vẫn ổn.
Đường dẫn DB lấy từ config.settings.db_path; schema được tạo ở lần kết nối đầu tiên.
"""
import sqlite3
import time
from contextlib import closing

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL    NOT NULL,          -- unix time (giây)
    honeypot   TEXT    NOT NULL,          -- 'ssh' | 'http'
    event_type TEXT    NOT NULL,          -- 'auth_attempt' | 'command' | 'http_login' ...
    src_ip     TEXT    NOT NULL,
    username   TEXT,
    password   TEXT,
    command    TEXT,
    user_agent TEXT,
    attack_tag TEXT                       -- vd: 'sqli', None nếu chưa phân loại
);
CREATE INDEX IF NOT EXISTS idx_events_ts  ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_ip  ON events(src_ip);
"""

_initialized = set()   # các file DB đã chạy SCHEMA trong tiến trình này


def _connect():
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")   # cho phép API đọc khi honeypot đang ghi
    if db_path not in _initialized:
        conn.executescript(SCHEMA)
        _initialized.add(db_path)
    return conn


def init_db():
    with closing(_connect()):
        pass


def log_event(honeypot, event_type, src_ip, username=None, password=None,
              command=None, user_agent=None, attack_tag=None):
    """Ghi 1 sự kiện. Không bao giờ để lỗi DB làm sập honeypot."""
    try:
        with closing(_connect()) as conn, conn:
            conn.execute(
                "INSERT INTO events (ts, honeypot, event_type, src_ip, username, "
                "password, command, user_agent, attack_tag) VALUES (?,?,?,?,?,?,?,?,?)",
                (time.time(), honeypot, event_type, src_ip, username, password,
                 command, user_agent, attack_tag),
            )
    except Exception as e:
        print(f"[event_store] lỗi ghi DB: {e}")


def query(sql, params=()):
    with closing(_connect()) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
