"""
DI Team — Agentic AI Readiness Survey
FastAPI + SQLite Backend  v2.0
Run: uvicorn main:app --reload --port 8000
  → Survey  : http://localhost:8000/
  → Admin   : http://localhost:8000/admin
  → API Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
import csv
import io
import os
import re

# ─────────────────────────────────────────────────────────────────────────────
# App & CORS
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="DI AI Survey API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = "di_survey.db"
ADMIN_PIN = "123456"
ADMIN_COOKIE = "di_admin"

SKILL_NAMES: List[str] = [
    "Prompt Engineering",
    "AI Agent / Agentic Workflow",
    "LangChain / LangGraph",
    "RAG & Vector DB",
    "MCP (Model Context Protocol)",
    "Cursor / AI-assisted IDE",
    "API Integration กับ LLM",
    "Data Pipeline + AI",
    "System Design สำหรับ AI",
    "AI Project Management",
]

TIER_ORDER = ["Beginner", "Awareness", "Practitioner", "Advanced", "Expert"]


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS survey_responses (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            yy                TEXT    DEFAULT '',
            mm                TEXT    DEFAULT '',
            email             TEXT    DEFAULT '',
            name              TEXT    NOT NULL,
            role              TEXT    DEFAULT '',
            team              TEXT    DEFAULT '',
            exp               TEXT    DEFAULT '',
            total_score       INTEGER DEFAULT 0,
            tier              TEXT    DEFAULT '',
            skills            TEXT    DEFAULT '{}',
            vibe_level        TEXT    DEFAULT '',
            vq1               TEXT    DEFAULT '',
            vq2               TEXT    DEFAULT '',
            vq3               TEXT    DEFAULT '',
            vibe_tools        TEXT    DEFAULT '[]',
            ai_tools          TEXT    DEFAULT '[]',
            is_high_potential INTEGER DEFAULT 0,
            interest          TEXT    DEFAULT '',
            learning_time     TEXT    DEFAULT '',
            comment           TEXT    DEFAULT '',
            created_at        TEXT    DEFAULT (datetime('now','localtime')),
            github_repos      TEXT    DEFAULT '[]'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            label      TEXT    NOT NULL,
            snapshot   TEXT    NOT NULL,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    # Lightweight migrations (add new columns when upgraded)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(survey_responses)").fetchall()]
    if "yy" not in cols:
        conn.execute("ALTER TABLE survey_responses ADD COLUMN yy TEXT DEFAULT ''")
    if "mm" not in cols:
        conn.execute("ALTER TABLE survey_responses ADD COLUMN mm TEXT DEFAULT ''")
    if "email" not in cols:
        conn.execute("ALTER TABLE survey_responses ADD COLUMN email TEXT DEFAULT ''")
    if "github_repos" not in cols:
        conn.execute("ALTER TABLE survey_responses ADD COLUMN github_repos TEXT DEFAULT '[]'")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_survey_yy_mm_email ON survey_responses(yy, mm, email)"
    )
    conn.commit()
    conn.close()


init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────
class SurveyPayload(BaseModel):
    yy: str
    mm: str
    email: str
    name: str
    role: Optional[str] = ""
    team: Optional[str] = ""
    exp: Optional[str] = ""
    total_score: Optional[int] = 0
    tier: Optional[str] = ""
    skills: Optional[dict] = {}
    vibe_level: Optional[str] = ""
    vq1: Optional[str] = ""
    vq2: Optional[str] = ""
    vq3: Optional[str] = ""
    vibe_tools: Optional[List[str]] = []
    ai_tools: Optional[List[str]] = []
    is_high_potential: Optional[bool] = False
    interest: Optional[str] = ""
    learning_time: Optional[str] = ""
    github_repos: Optional[List[str]] = []


class SnapshotPayload(BaseModel):
    label: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key, default in [("skills", "{}"), ("vibe_tools", "[]"), ("ai_tools", "[]"), ("github_repos", "[]")]:
        try:
            d[key] = json.loads(d.get(key) or default)
        except Exception:
            d[key] = json.loads(default)
    d["is_high_potential"] = bool(d.get("is_high_potential", 0))
    return d


def build_values(payload: SurveyPayload) -> tuple:
    return (
        (payload.yy or "").strip(),
        (payload.mm or "").strip(),
        (payload.email or "").strip(),
        payload.role or "",
        payload.team or "",
        payload.exp or "",
        payload.total_score or 0,
        payload.tier or "",
        json.dumps(payload.skills or {}, ensure_ascii=False),
        payload.vibe_level or "",
        payload.vq1 or "",
        payload.vq2 or "",
        payload.vq3 or "",
        json.dumps(payload.vibe_tools or [], ensure_ascii=False),
        json.dumps(payload.ai_tools or [], ensure_ascii=False),
        1 if payload.is_high_potential else 0,
        payload.interest or "",
        payload.learning_time or "",
        json.dumps(payload.github_repos or [], ensure_ascii=False),
    )


def assert_admin(request: Request) -> None:
    if request.cookies.get(ADMIN_COOKIE) != "1":
        raise HTTPException(status_code=401, detail="ต้องใส่ PIN สำหรับ Admin")


class AdminLoginPayload(BaseModel):
    pin: str


def build_group_summary(members: list, key: str, value: str) -> dict:
    """Build aggregate summary for a group (team or role)."""
    m = len(members)
    if m == 0:
        return {}
    skill_avg = {
        sk: round(sum(r["skills"].get(sk, 0) for r in members) / m, 2)
        for sk in SKILL_NAMES
    }
    tier_dist: dict = {}
    for r in members:
        t = r["tier"] or "—"
        tier_dist[t] = tier_dist.get(t, 0) + 1
    hp_count = sum(1 for r in members if r["is_high_potential"])
    return {
        key: value,
        "count": m,
        "avg_score": round(sum(r["total_score"] for r in members) / m, 1),
        "hp_count": hp_count,
        "hp_pct": round(hp_count / m * 100),
        "tier_dist": tier_dist,
        "skill_avg": skill_avg,
        "members": [
            {
                "name": r["name"],
                "role": r["role"],
                "team": r["team"],
                "exp": r["exp"],
                "total_score": r["total_score"],
                "tier": r["tier"],
                "vibe_level": r["vibe_level"],
                "is_high_potential": r["is_high_potential"],
                "skills": r["skills"],
            }
            for r in sorted(members, key=lambda x: x["total_score"], reverse=True)
        ],
    }


def compute_full_summary(data: list) -> dict:
    """Compute complete summary used both for /api/summary and snapshots."""
    n = len(data)
    if n == 0:
        return {"total": 0}

    avg_score = round(sum(r["total_score"] for r in data) / n, 1)
    hp_count = sum(1 for r in data if r["is_high_potential"])

    tier_dist: dict = {}
    for r in data:
        t = r["tier"] or "—"
        tier_dist[t] = tier_dist.get(t, 0) + 1

    vibe_dist: dict = {}
    for r in data:
        vl = r["vibe_level"] or "-"
        vibe_dist[vl] = vibe_dist.get(vl, 0) + 1

    skill_avg = {
        sk: round(sum(r["skills"].get(sk, 0) for r in data) / n, 2)
        for sk in SKILL_NAMES
    }

    # Group by team
    team_map: dict = {}
    for r in data:
        t = r["team"] or "—"
        team_map.setdefault(t, []).append(r)

    team_summary = {
        t: build_group_summary(members, "team", t)
        for t, members in team_map.items()
    }

    # Group by role
    role_map: dict = {}
    for r in data:
        rl = r["role"] or "—"
        role_map.setdefault(rl, []).append(r)

    role_summary = {
        rl: build_group_summary(members, "role", rl)
        for rl, members in role_map.items()
    }

    return {
        "total": n,
        "avg_score": avg_score,
        "hp_count": hp_count,
        "hp_pct": round(hp_count / n * 100),
        "tier_dist": tier_dist,
        "vibe_dist": vibe_dist,
        "skill_avg": skill_avg,
        "team_summary": team_summary,
        "role_summary": role_summary,
    }


def norm_yy_mm(yy: str, mm: str) -> tuple[str, str]:
    yy = (yy or "").strip()
    mm = (mm or "").strip()
    if not re.fullmatch(r"\d{2}", yy):
        raise HTTPException(status_code=400, detail="YY ต้องเป็นตัวเลข 2 หลัก เช่น 26")
    if not re.fullmatch(r"\d{2}", mm) or not (1 <= int(mm) <= 12):
        raise HTTPException(status_code=400, detail="MM ต้องเป็น 01-12")
    return yy, mm


# ─────────────────────────────────────────────────────────────────────────────
# Serve Pages
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_survey():
    f = "di_ai_survey_with_dashboard.html"
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html; charset=utf-8")
    return {"message": f"วางไฟล์ {f} ไว้ในโฟลเดอร์เดียวกับ main.py"}


@app.get("/admin", include_in_schema=False)
def serve_admin():
    f = "admin.html"
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html; charset=utf-8")
    return {"message": "วางไฟล์ admin.html ไว้ในโฟลเดอร์เดียวกับ main.py"}


# ─────────────────────────────────────────────────────────────────────────────
# Admin PIN Auth (simple cookie session)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/admin/me")
def admin_me(request: Request):
    return {"ok": request.cookies.get(ADMIN_COOKIE) == "1"}


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginPayload, response: Response):
    if (payload.pin or "").strip() != ADMIN_PIN:
        raise HTTPException(status_code=401, detail="PIN ไม่ถูกต้อง")
    response.set_cookie(
        key=ADMIN_COOKIE,
        value="1",
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return {"ok": True}


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(key=ADMIN_COOKIE)
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Survey CRUD
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/survey")
def save_survey(payload: SurveyPayload):
    conn = get_db()
    try:
        yy = (payload.yy or "").strip()
        mm = (payload.mm or "").strip()
        email = (payload.email or "").strip()
        if not yy or not mm or not email:
            raise HTTPException(status_code=400, detail="ต้องระบุ YY, MM, Email")
        existing = conn.execute(
            "SELECT id FROM survey_responses WHERE yy = ? AND mm = ? AND email = ?",
            (yy, mm, email),
        ).fetchone()
        values = build_values(payload)

        if existing:
            conn.execute(
                """UPDATE survey_responses SET
                       yy=?, mm=?, email=?,
                       role=?, team=?, exp=?, total_score=?, tier=?,
                       skills=?, vibe_level=?, vq1=?, vq2=?, vq3=?,
                       vibe_tools=?, ai_tools=?, is_high_potential=?,
                       interest=?, learning_time=?, github_repos=?,
                       created_at=datetime('now','localtime')
                   WHERE yy=? AND mm=? AND email=?""",
                (*values, yy, mm, email),
            )
            record_id = existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO survey_responses
                       (yy, mm, email, role, team, exp, total_score, tier, skills, vibe_level,
                        vq1, vq2, vq3, vibe_tools, ai_tools, is_high_potential,
                        interest, learning_time, github_repos, name)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (*values, payload.name),
            )
            record_id = cur.lastrowid

        conn.commit()
        return {"ok": True, "id": record_id, "message": f"บันทึกข้อมูลของ '{payload.name}' ({yy}-{mm}, {email}) เรียบร้อย"}
    finally:
        conn.close()


@app.get("/api/survey")
def get_all_surveys(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM survey_responses ORDER BY total_score DESC"
        ).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


@app.delete("/api/survey/{record_id}")
def delete_survey(record_id: int, request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        result = conn.execute("DELETE FROM survey_responses WHERE id = ?", (record_id,))
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล")
        return {"ok": True, "message": f"ลบข้อมูล id={record_id} เรียบร้อย"}
    finally:
        conn.close()


@app.delete("/api/survey")
def delete_all_surveys(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        conn.execute("DELETE FROM survey_responses")
        conn.commit()
        return {"ok": True, "message": "ล้างข้อมูลทั้งหมดเรียบร้อย"}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Summary Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/summary")
def get_summary(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM survey_responses").fetchall()
        data = [row_to_dict(r) for r in rows]
        return compute_full_summary(data)
    finally:
        conn.close()


@app.get("/api/summary/month")
def get_summary_by_month(yy: str, mm: str, request: Request):
    assert_admin(request)
    yy, mm = norm_yy_mm(yy, mm)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM survey_responses WHERE yy = ? AND mm = ?",
            (yy, mm),
        ).fetchall()
        data = [row_to_dict(r) for r in rows]
        s = compute_full_summary(data)
        s["yy"] = yy
        s["mm"] = mm
        return s
    finally:
        conn.close()


@app.get("/api/months")
def list_months(request: Request):
    """List available months (yy-mm) that have at least one response."""
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT yy, mm, COUNT(*) AS count,
                   ROUND(AVG(total_score), 1) AS avg_score,
                   SUM(CASE WHEN is_high_potential = 1 THEN 1 ELSE 0 END) AS hp_count
            FROM survey_responses
            WHERE TRIM(yy) <> '' AND TRIM(mm) <> '' AND TRIM(email) <> ''
            GROUP BY yy, mm
            ORDER BY yy ASC, mm ASC
            """
        ).fetchall()
        out = []
        for r in rows:
            total = int(r["count"] or 0)
            hp = int(r["hp_count"] or 0)
            out.append(
                {
                    "yy": r["yy"],
                    "mm": r["mm"],
                    "label": f"{r['yy']}-{r['mm']}",
                    "count": total,
                    "avg_score": float(r["avg_score"] or 0),
                    "hp_count": hp,
                    "hp_pct": round(hp / total * 100) if total else 0,
                }
            )
        return out
    finally:
        conn.close()


@app.get("/api/summary/team")
def summary_by_team(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM survey_responses").fetchall()
        data = [row_to_dict(r) for r in rows]
        team_map: dict = {}
        for r in data:
            team_map.setdefault(r["team"] or "—", []).append(r)
        return [
            build_group_summary(members, "team", team)
            for team, members in sorted(team_map.items())
        ]
    finally:
        conn.close()


@app.get("/api/summary/role")
def summary_by_role(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM survey_responses").fetchall()
        data = [row_to_dict(r) for r in rows]
        role_map: dict = {}
        for r in data:
            role_map.setdefault(r["role"] or "—", []).append(r)
        return [
            build_group_summary(members, "role", role)
            for role, members in sorted(role_map.items())
        ]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Export CSV
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/export/csv")
def export_csv(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM survey_responses ORDER BY total_score DESC"
        ).fetchall()
        data = [row_to_dict(r) for r in rows]

        output = io.StringIO()
        headers = (
            ["id", "ชื่อ", "ตำแหน่ง", "ทีม", "ประสบการณ์",
             "คะแนน", "ระดับ", "Vibe Level", "High-potential",
             "Vibe Tools", "AI Tools", "สนใจพัฒนา",
             "เวลาเรียนรู้", "GitHub repo", "วันที่"]
            + SKILL_NAMES
        )
        writer = csv.writer(output)
        writer.writerow(headers)
        for r in data:
            writer.writerow(
                [r["id"], r["name"], r["role"], r["team"], r["exp"],
                 r["total_score"], r["tier"], r["vibe_level"],
                 "ใช่" if r["is_high_potential"] else "ไม่",
                 "|".join(r["vibe_tools"]),
                 "|".join(r["ai_tools"]),
                 r["interest"], r["learning_time"],
                 ",".join(r.get("github_repos") or []), r["created_at"]]
                + [r["skills"].get(sk, 0) for sk in SKILL_NAMES]
            )

        content = b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="di_ai_readiness_survey.csv"'},
        )
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Snapshots (Monthly Tracking)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/snapshot")
def create_snapshot(payload: SnapshotPayload, request: Request):
    assert_admin(request)
    if not payload.label.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อ Snapshot")
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM survey_responses").fetchall()
        data = [row_to_dict(r) for r in rows]
        if not data:
            raise HTTPException(status_code=400, detail="ไม่มีข้อมูลสำหรับบันทึก Snapshot")

        summary = compute_full_summary(data)
        # Add individual list to snapshot
        summary["individuals"] = [
            {
                "name": r["name"], "role": r["role"], "team": r["team"],
                "total_score": r["total_score"], "tier": r["tier"],
                "vibe_level": r["vibe_level"],
                "is_high_potential": r["is_high_potential"],
                "skills": r["skills"],
            }
            for r in sorted(data, key=lambda x: x["total_score"], reverse=True)
        ]

        cur = conn.execute(
            "INSERT INTO snapshots (label, snapshot) VALUES (?, ?)",
            (payload.label.strip(), json.dumps(summary, ensure_ascii=False)),
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid, "message": f"บันทึก Snapshot '{payload.label}' เรียบร้อย"}
    finally:
        conn.close()


@app.get("/api/snapshots")
def get_snapshots(request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, label, created_at FROM snapshots ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/snapshots/{snap_id}")
def get_snapshot(snap_id: int, request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snap_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="ไม่พบ Snapshot")
        d = dict(row)
        d["snapshot"] = json.loads(d["snapshot"])
        return d
    finally:
        conn.close()


@app.delete("/api/snapshots/{snap_id}")
def delete_snapshot(snap_id: int, request: Request):
    assert_admin(request)
    conn = get_db()
    try:
        result = conn.execute("DELETE FROM snapshots WHERE id = ?", (snap_id,))
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="ไม่พบ Snapshot")
        return {"ok": True, "message": "ลบ Snapshot เรียบร้อย"}
    finally:
        conn.close()
