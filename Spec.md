ฉันมีไฟล์ HTML Survey Form ชื่อ "di_ai_survey_with_dashboard.html" 
ต้องการพัฒนาต่อเป็น Full-stack Web App โดยเพิ่ม SQLite Database Backend
## สิ่งที่ต้องการ
### Backend (Python FastAPI + SQLite)
- สร้าง FastAPI server
- สร้าง SQLite database ชื่อ "di_survey.db"
- Table: survey_responses เก็บข้อมูลจาก Form ทั้งหมด
  - id, name, role, team, exp
  - total_score, tier
  - skills (JSON) — 10 ทักษะ Agentic AI พร้อมคะแนน 0-4
  - vibe_level, vq1, vq2, vq3
  - vibe_tools (JSON Array)
  - ai_tools (JSON Array)  
  - is_high_potential (Boolean)
  - interest, learning_time, comment
  - created_at (timestamp)
- REST API Endpoints:
  - POST /api/survey — บันทึกข้อมูลใหม่ (upsert by name)
  - GET  /api/survey — ดึงข้อมูลทั้งหมด
  - GET  /api/summary — สรุป aggregate (avg score, tier dist, vibe dist, skill avg)
  - GET  /api/export/csv — download CSV
  - DELETE /api/survey/{id} — ลบรายการ
### Frontend
- แก้ไขไฟล์ HTML เดิม ให้เรียก API แทน localStorage
- Submit Form → POST /api/survey
- Dashboard → GET /api/summary + GET /api/survey
- Export CSV → GET /api/export/csv
- เพิ่มปุ่ม "ลบ" รายบุคคลใน Dashboard table
### Requirements
- Python 3.11+
- FastAPI, uvicorn, sqlite3 (built-in)
- CORS enabled สำหรับ localhost
- สร้าง requirements.txt
- สร้าง README วิธีรัน
### Run command
uvicorn main:app --reload --port 8000