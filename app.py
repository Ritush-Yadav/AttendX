"""
app.py — Face Recognition Attendance System

A Flask dashboard that wraps an OpenCV LBPH face recognizer:
  - enroll students and capture face samples through the browser's webcam
  - train the recognizer from the collected dataset
  - scan a webcam feed and mark attendance automatically on a match
  - view dashboard analytics, attendance history and CSV exports

Run with:
    python app.py
Then open http://127.0.0.1:5000
Default login: admin / admin123  (change ADMIN_PASSWORD below before real use)
"""

import csv
import io
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import cv2
import numpy as np
from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from face_utils import (
    crop_and_normalize,
    decode_base64_image,
    detect_largest_face,
    next_sample_index,
    student_dataset_dir,
)
from train_model import TRAINER_PATH, train as train_recognizer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

COLLEGE_NAME = "Ridgeview Institute of Technology"
COLLEGE_SHORT = "RIT"
SYSTEM_NAME = "AttendX"

TARGET_SAMPLES = 40          # face samples captured per student
RECOGNITION_THRESHOLD = 75   # LBPH distance: lower = stricter match required

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # change this before deploying anywhere real

app = Flask(__name__)
app.secret_key = os.environ.get("ATTENDX_SECRET_KEY", "dev-secret-change-me")

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

_recognizer_cache = {"mtime": None, "model": None}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    first_run = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            department TEXT,
            year TEXT,
            samples_captured INTEGER DEFAULT 0,
            trained INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(student_id, date)
        );

        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """
    )
    if first_run:
        conn.execute(
            "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
            (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD)),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "college_name": COLLEGE_NAME,
        "college_short": COLLEGE_SHORT,
        "system_name": SYSTEM_NAME,
        "now": datetime.now(),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Incorrect username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("admin_logged_in") else url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/stats")
@login_required
def api_stats():
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    total_students = db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    present_today = db.execute(
        "SELECT COUNT(DISTINCT student_id) c FROM attendance WHERE date = ?", (today,)
    ).fetchone()["c"]
    trained_students = db.execute(
        "SELECT COUNT(*) c FROM students WHERE trained = 1"
    ).fetchone()["c"]
    absent_today = max(total_students - present_today, 0)
    rate = round((present_today / total_students) * 100, 1) if total_students else 0.0

    return jsonify(
        {
            "total_students": total_students,
            "present_today": present_today,
            "absent_today": absent_today,
            "trained_students": trained_students,
            "attendance_rate": rate,
        }
    )


@app.route("/api/attendance-trend")
@login_required
def api_attendance_trend():
    db = get_db()
    days = []
    counts = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        label = (datetime.now() - timedelta(days=i)).strftime("%a")
        count = db.execute(
            "SELECT COUNT(DISTINCT student_id) c FROM attendance WHERE date = ?", (day,)
        ).fetchone()["c"]
        days.append(label)
        counts.append(count)
    return jsonify({"labels": days, "values": counts})


@app.route("/api/department-breakdown")
@login_required
def api_department_breakdown():
    db = get_db()
    rows = db.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(department), ''), 'Unassigned') AS department, COUNT(*) c
        FROM students GROUP BY department ORDER BY c DESC
        """
    ).fetchall()
    return jsonify(
        {"labels": [r["department"] for r in rows], "values": [r["c"] for r in rows]}
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@app.route("/students")
@login_required
def students():
    db = get_db()
    query = request.args.get("q", "").strip()
    if query:
        rows = db.execute(
            """
            SELECT * FROM students
            WHERE name LIKE ? OR roll_no LIKE ? OR department LIKE ?
            ORDER BY created_at DESC
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    return render_template("students.html", students=rows, query=query, target_samples=TARGET_SAMPLES)


@app.route("/students/add", methods=["POST"])
@login_required
def students_add():
    db = get_db()
    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()
    year = request.form.get("year", "").strip()

    if not name or not roll_no:
        return jsonify({"ok": False, "message": "Name and roll number are required."}), 400

    try:
        cur = db.execute(
            "INSERT INTO students (roll_no, name, email, department, year) VALUES (?, ?, ?, ?, ?)",
            (roll_no, name, email, department, year),
        )
        db.commit()
        student_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "message": f"Roll number '{roll_no}' already exists."}), 400

    return jsonify({"ok": True, "student_id": student_id})


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@login_required
def students_delete(student_id):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()

    student_dir = os.path.join(DATASET_DIR, str(student_id))
    if os.path.isdir(student_dir):
        for f in os.listdir(student_dir):
            os.remove(os.path.join(student_dir, f))
        os.rmdir(student_dir)

    return jsonify({"ok": True})


@app.route("/api/student/<int:student_id>")
@login_required
def api_student_detail(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404

    history = db.execute(
        """
        SELECT date, time, confidence FROM attendance
        WHERE student_id = ? ORDER BY date DESC, time DESC LIMIT 10
        """,
        (student_id,),
    ).fetchall()
    total_present = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE student_id = ?", (student_id,)
    ).fetchone()["c"]

    return jsonify(
        {
            "ok": True,
            "student": dict(student),
            "total_present": total_present,
            "history": [dict(h) for h in history],
        }
    )


# ---------------------------------------------------------------------------
# Capture (enrollment)
# ---------------------------------------------------------------------------

@app.route("/capture/<int:student_id>")
@login_required
def capture_page(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        return redirect(url_for("students"))
    return render_template("capture.html", student=student, target_samples=TARGET_SAMPLES)


@app.route("/api/capture/<int:student_id>", methods=["POST"])
@login_required
def api_capture_frame(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image")
    if not image_data:
        return jsonify({"ok": False, "message": "No frame received."}), 400

    frame = decode_base64_image(image_data)
    if frame is None:
        return jsonify({"ok": False, "message": "Could not decode frame."}), 400

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box = detect_largest_face(gray)
    if box is None:
        return jsonify({"ok": True, "face_found": False, "saved": student["samples_captured"]})

    student_dir = student_dataset_dir(DATASET_DIR, student_id)
    face = crop_and_normalize(gray, box)
    idx = next_sample_index(student_dir)
    cv2.imwrite(os.path.join(student_dir, f"{idx}.jpg"), face)

    new_count = idx
    db.execute("UPDATE students SET samples_captured = ? WHERE id = ?", (new_count, student_id))
    db.commit()

    x, y, w, h = [int(v) for v in box]
    return jsonify(
        {
            "ok": True,
            "face_found": True,
            "saved": new_count,
            "target": TARGET_SAMPLES,
            "box": {"x": x, "y": y, "w": w, "h": h},
            "complete": new_count >= TARGET_SAMPLES,
        }
    )


@app.route("/api/train", methods=["POST"])
@login_required
def api_train():
    result = train_recognizer()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Scan (mark attendance)
# ---------------------------------------------------------------------------

@app.route("/scan")
@login_required
def scan_page():
    return render_template("scan.html")


def _load_recognizer():
    if not os.path.exists(TRAINER_PATH):
        return None
    mtime = os.path.getmtime(TRAINER_PATH)
    if _recognizer_cache["model"] is None or _recognizer_cache["mtime"] != mtime:
        model = cv2.face.LBPHFaceRecognizer_create()
        model.read(TRAINER_PATH)
        _recognizer_cache["model"] = model
        _recognizer_cache["mtime"] = mtime
    return _recognizer_cache["model"]


@app.route("/api/recognize", methods=["POST"])
@login_required
def api_recognize():
    db = get_db()
    recognizer = _load_recognizer()
    if recognizer is None:
        return jsonify({"ok": False, "message": "Model not trained yet."}), 400

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image")
    if not image_data:
        return jsonify({"ok": False, "message": "No frame received."}), 400

    frame = decode_base64_image(image_data)
    if frame is None:
        return jsonify({"ok": False, "message": "Could not decode frame."}), 400

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box = detect_largest_face(gray)
    if box is None:
        return jsonify({"ok": True, "face_found": False})

    face = crop_and_normalize(gray, box)
    label, confidence = recognizer.predict(face)
    x, y, w, h = [int(v) for v in box]
    box_out = {"x": x, "y": y, "w": w, "h": h}

    if confidence > RECOGNITION_THRESHOLD:
        return jsonify(
            {"ok": True, "face_found": True, "recognized": False, "confidence": round(confidence, 1), "box": box_out}
        )

    student = db.execute("SELECT * FROM students WHERE id = ?", (label,)).fetchone()
    if not student:
        return jsonify(
            {"ok": True, "face_found": True, "recognized": False, "confidence": round(confidence, 1), "box": box_out}
        )

    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    already_marked = db.execute(
        "SELECT 1 FROM attendance WHERE student_id = ? AND date = ?", (student["id"], today)
    ).fetchone()

    if not already_marked:
        db.execute(
            "INSERT INTO attendance (student_id, date, time, confidence) VALUES (?, ?, ?, ?)",
            (student["id"], today, now_time, confidence),
        )
        db.commit()

    return jsonify(
        {
            "ok": True,
            "face_found": True,
            "recognized": True,
            "confidence": round(confidence, 1),
            "box": box_out,
            "already_marked": bool(already_marked),
            "student": {
                "id": student["id"],
                "name": student["name"],
                "roll_no": student["roll_no"],
                "department": student["department"],
                "year": student["year"],
            },
            "time": now_time,
        }
    )


# ---------------------------------------------------------------------------
# Attendance history + export
# ---------------------------------------------------------------------------

@app.route("/attendance")
@login_required
def attendance():
    db = get_db()
    date_filter = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = db.execute(
        """
        SELECT a.*, s.name, s.roll_no, s.department
        FROM attendance a JOIN students s ON s.id = a.student_id
        WHERE a.date = ?
        ORDER BY a.time DESC
        """,
        (date_filter,),
    ).fetchall()
    return render_template("attendance.html", records=rows, date_filter=date_filter)


@app.route("/export/csv")
@login_required
def export_csv():
    db = get_db()
    date_filter = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = db.execute(
        """
        SELECT s.roll_no, s.name, s.department, s.year, a.date, a.time, a.confidence
        FROM attendance a JOIN students s ON s.id = a.student_id
        WHERE a.date = ?
        ORDER BY a.time ASC
        """,
        (date_filter,),
    ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Roll No", "Name", "Department", "Year", "Date", "Time", "Confidence"])
    for r in rows:
        writer.writerow([r["roll_no"], r["name"], r["department"], r["year"], r["date"], r["time"], r["confidence"]])

    mem = io.BytesIO(buffer.getvalue().encode("utf-8"))
    filename = f"attendance_{date_filter}.csv"
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)
