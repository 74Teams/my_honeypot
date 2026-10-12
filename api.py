"""
api.py - REST API (FastAPI) cho dữ liệu honeypot.

Chạy:   uvicorn api:app --host 127.0.0.1 --port 8000
Docs:   http://127.0.0.1:8000/docs   (FastAPI tự sinh trang thử API)
"""
import time
from typing import Optional

from fastapi import FastAPI, Query

from event_store import query

app = FastAPI(title="HONEYPY API", version="0.1")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/events")
def list_events(
    honeypot: Optional[str] = Query(None, description="ssh | http"),
    event_type: Optional[str] = None,
    src_ip: Optional[str] = None,
    since_minutes: Optional[int] = Query(None, ge=1, description="chỉ lấy N phút gần nhất"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Danh sách sự kiện, lọc theo honeypot / loại / IP / thời gian."""
    where, params = [], []
    if honeypot:
        where.append("honeypot = ?"); params.append(honeypot)
    if event_type:
        where.append("event_type = ?"); params.append(event_type)
    if src_ip:
        where.append("src_ip = ?"); params.append(src_ip)
    if since_minutes:
        where.append("ts >= ?"); params.append(time.time() - since_minutes * 60)

    sql = "SELECT * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    return query(sql, params)


@app.get("/stats/summary")
def summary():
    """Số liệu tổng quan cho báo cáo."""
    total = query("SELECT COUNT(*) AS n FROM events")[0]["n"]
    ips = query("SELECT COUNT(DISTINCT src_ip) AS n FROM events")[0]["n"]
    by_type = query("SELECT honeypot, event_type, COUNT(*) AS n FROM events "
                    "GROUP BY honeypot, event_type ORDER BY n DESC")
    return {"total_events": total, "unique_ips": ips, "by_type": by_type}


@app.get("/stats/top-ips")
def top_ips(limit: int = Query(10, ge=1, le=100)):
    return query("SELECT src_ip, COUNT(*) AS events FROM events "
                 "GROUP BY src_ip ORDER BY events DESC LIMIT ?", (limit,))


@app.get("/stats/top-credentials")
def top_credentials(limit: int = Query(10, ge=1, le=100)):
    """Cặp username/password bị thử nhiều nhất (từ cả SSH và HTTP)."""
    return query("SELECT username, password, COUNT(*) AS attempts FROM events "
                 "WHERE username IS NOT NULL "
                 "GROUP BY username, password ORDER BY attempts DESC LIMIT ?", (limit,))


@app.get("/stats/bruteforce")
def bruteforce(
    window_minutes: int = Query(10, ge=1, le=1440),
    threshold: int = Query(5, ge=2, description="từ bao nhiêu lần thử trở lên thì coi là brute-force"),
):
    """IP có số lần thử đăng nhập >= threshold trong cửa sổ thời gian gần đây."""
    since = time.time() - window_minutes * 60
    return query(
        "SELECT src_ip, COUNT(*) AS attempts, "
        "COUNT(DISTINCT username) AS distinct_users, "
        "COUNT(DISTINCT password) AS distinct_passwords, "
        "MIN(ts) AS first_seen, MAX(ts) AS last_seen "
        "FROM events WHERE event_type IN ('auth_attempt','http_login') AND ts >= ? "
        "GROUP BY src_ip HAVING attempts >= ? ORDER BY attempts DESC",
        (since, threshold),
    )
