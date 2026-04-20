# DI Team — Agentic AI Readiness Survey (Full-stack)

ระบบ Survey + Dashboard สำหรับประเมินความพร้อม Agentic AI ของทีม DI  
**Stack:** Python FastAPI + SQLite (Backend) + Vanilla HTML/JS (Frontend)

---

## โครงสร้างไฟล์

```
22.DI Question/
├── main.py                              ← FastAPI server
├── requirements.txt                     ← Python dependencies
├── di_ai_survey_with_dashboard.html     ← Frontend (Survey + Dashboard)
├── di_survey.db                         ← SQLite database (สร้างอัตโนมัติ)
└── README.md
```

---

## วิธีติดตั้งและรัน

### 1. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 2. รัน Server

```bash
uvicorn main:app --reload --port 8000
```

### 3. เปิด Browser

ไปที่ → **http://localhost:8000**

> ระบบจะเสิร์ฟ HTML อัตโนมัติ ไม่ต้องเปิดไฟล์แยก

### Admin Dashboard

- **URL**: http://localhost:8000/admin
- **PIN (fix)**: `123456`

> หมายเหตุ: หน้า Admin และ API ที่ใช้แสดง Dashboard ถูกป้องกันด้วย PIN (cookie session)

---

## API Endpoints

| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| `POST` | `/api/survey` | บันทึก / อัปเดต (replace ด้วย key: `YY+MM+Email`) |
| `GET` | `/api/survey` | ดึงข้อมูลทั้งหมด เรียงตามคะแนน *(Admin PIN required)* |
| `GET` | `/api/summary` | สรุป aggregate (avg, tier dist, skill avg) *(Admin PIN required)* |
| `GET` | `/api/summary/month?yy=YY&mm=MM` | สรุปรายเดือน (เช่น `yy=26&mm=04`) *(Admin PIN required)* |
| `GET` | `/api/months` | รายการเดือนที่มีข้อมูล + metrics เบื้องต้น *(Admin PIN required)* |
| `GET` | `/api/export/csv` | ดาวน์โหลด CSV (UTF-8 BOM, Excel-ready) *(Admin PIN required)* |
| `DELETE` | `/api/survey/{id}` | ลบรายการตาม id *(Admin PIN required)* |
| `DELETE` | `/api/survey` | ล้างข้อมูลทั้งหมด *(Admin PIN required)* |

### Admin Auth

| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| `GET` | `/api/admin/me` | ตรวจว่า login แล้วหรือยัง |
| `POST` | `/api/admin/login` | login ด้วย PIN `{ "pin": "123456" }` |
| `POST` | `/api/admin/logout` | logout

### API Docs (Swagger UI)
http://localhost:8000/docs

---

## Database Schema

ไฟล์: `di_survey.db` (สร้างอัตโนมัติเมื่อรัน server ครั้งแรก)

| Column | Type | คำอธิบาย |
|--------|------|----------|
| `id` | INTEGER PK | Auto-increment |
| `yy` | TEXT | ปีที่ตอบ (YY) |
| `mm` | TEXT | เดือนที่ตอบ (MM) |
| `email` | TEXT | Email (ใช้ร่วมกับ YY/MM เป็น key สำหรับ replace) |
| `name` | TEXT | ชื่อ |
| `role` | TEXT | ตำแหน่ง |
| `team` | TEXT | ทีม |
| `exp` | TEXT | ประสบการณ์ |
| `total_score` | INTEGER | คะแนนรวม 0–40 |
| `tier` | TEXT | Beginner / Awareness / Practitioner / Advanced / Expert |
| `skills` | TEXT (JSON) | คะแนนทักษะ 10 ด้าน |
| `vibe_level` | TEXT | Viewer / Learner / Vibe Coder / Power Vibe |
| `vq1–vq3` | TEXT | คำตอบ Vibe Coding questions |
| `vibe_tools` | TEXT (JSON) | เครื่องมือ Vibe Coding |
| `ai_tools` | TEXT (JSON) | เครื่องมือ AI อื่นๆ |
| `is_high_potential` | INTEGER | 1=HP, 0=ไม่ |
| `interest` | TEXT | ด้านที่อยากพัฒนา |
| `learning_time` | TEXT | เวลาเรียนรู้ต่อสัปดาห์ |
| `github_repos` | TEXT (JSON) | GitHub repo (มากกว่า 1 คั่นด้วย comma จากฟอร์ม) |
| `comment` | TEXT | (legacy) ข้อเสนอแนะ |
| `created_at` | TEXT | วันที่บันทึก |

---

## หมายเหตุ

- ข้อมูลถูก **replace (upsert)** ด้วย key: `YY + MM + Email`
- SQLite built-in ใน Python ไม่ต้องติดตั้งเพิ่ม
- CORS เปิดไว้สำหรับทุก origin (ปรับได้ใน `main.py`)
