# AttendX — Face Recognition Attendance System

A Flask + OpenCV attendance dashboard: enroll students by capturing face
samples through the browser's webcam, train an LBPH recognizer, then run a
live scanner that marks attendance automatically on a match.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Default login is `admin` / `admin123` —
change `ADMIN_PASSWORD` in `app.py` (or delete `database.db` after changing
it) before using this anywhere beyond your own machine.

The database, dataset images and trained model are created automatically on
first run:

```
database.db      SQLite: students, attendance, admin
dataset/<id>/    Captured face crops per student (created on first capture)
trainer/         trainer.yml — the trained LBPH model
exports/         Reserved for generated exports
```

## Using it

1. **Students → Add Student** — enter name, roll number, department, year.
   You're taken straight to the capture screen.
2. **Capture Faces** — click *Start Capture*, look at the camera and slowly
   turn your head; it saves ~40 samples automatically, then click
   **Train Recognition Model**.
3. **Scan Attendance** — click *Start Scanner*. Recognized students are
   marked present for the day (once per day) and appear in the live feed.
4. **Attendance Log** — filter by date, export to CSV.
5. Click any row in **Students** to open a profile modal with dataset
   progress and recent attendance.

## Two ways to capture faces

- **Web dashboard** (`app.py` → `/capture/<id>`): the *browser's* webcam
  streams frames to the server over the network, so this is what you use
  when the app is deployed somewhere and admins connect from their own
  machines.
- **`capture_faces.py`** (CLI): for a local machine that has a webcam
  physically attached to it (e.g. a single lab PC running everything). Run:

  ```bash
  python capture_faces.py --id 3 --name "Ada Lovelace" --samples 40
  ```

Both paths write into the same `dataset/<student_id>/` folders and share
detection logic from `face_utils.py`, so either (or both) can feed
`train_model.py` / the **Train Recognition Model** button.

## Notes on the recognition model

- Detection: OpenCV's bundled Haar cascade (`haarcascade_frontalface_default.xml`).
- Recognition: `cv2.face.LBPHFaceRecognizer` — lightweight, no GPU or
  external model download required, good enough for a small enrolled
  population (tens to low hundreds of students) in reasonably consistent
  lighting.
- `RECOGNITION_THRESHOLD` in `app.py` controls strictness (LBPH reports a
  *distance*, so lower = stricter). Tune it if you're seeing false accepts
  or too many "not recognized" results.
- The model is retrained from scratch on every **Train** click using every
  sample under `dataset/`, so re-run it after adding or removing students.

## Tech

Flask, SQLite (stdlib `sqlite3`), OpenCV (`opencv-contrib-python` for the
`cv2.face` module), vanilla JS + Chart.js for the dashboard — no frontend
build step.
