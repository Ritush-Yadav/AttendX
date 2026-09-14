"""
capture_faces.py

Standalone CLI utility for capturing a student's face dataset using a webcam
that is physically attached to the machine running this script.

The web dashboard (app.py) has its own browser-based capture flow — it asks the
*visiting browser's* webcam for frames and posts them to /api/capture/<id>. Use
that when running the app on a server. Use this script instead when you're
sitting at the same machine as the camera (e.g. running everything on one lab
PC) and want to capture a dataset without opening the web UI.

Usage:
    python capture_faces.py --id 3 --name "Ada Lovelace" --samples 40
"""

import argparse
import os
import sqlite3
import sys
import time

import cv2

from face_utils import (
    crop_and_normalize,
    detect_largest_face,
    get_face_cascade,
    next_sample_index,
    student_dataset_dir,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")


def update_sample_count(student_id, count):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE students SET samples_captured = ? WHERE id = ?", (count, student_id)
    )
    conn.commit()
    conn.close()


def capture(student_id, target_samples=40, camera_index=0):
    get_face_cascade()  # warm up / fail fast if cascade is missing
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Could not open camera index {camera_index}.", file=sys.stderr)
        sys.exit(1)

    student_dir = student_dataset_dir(DATASET_DIR, student_id)
    saved = next_sample_index(student_dir) - 1
    print(f"Capturing face samples for student {student_id}. Press 'q' to stop early.")

    last_save = 0
    while saved < target_samples:
        ok, frame = cap.read()
        if not ok:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        box = detect_largest_face(gray)

        display = frame.copy()
        if box is not None:
            x, y, w, h = box
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 220, 130), 2)

            # Throttle saves so we get varied poses instead of near-duplicate frames.
            if time.time() - last_save > 0.25:
                face = crop_and_normalize(gray, box)
                idx = next_sample_index(student_dir)
                cv2.imwrite(os.path.join(student_dir, f"{idx}.jpg"), face)
                saved += 1
                last_save = time.time()
                update_sample_count(student_id, saved)

        cv2.putText(
            display,
            f"Samples: {saved}/{target_samples}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 220, 130),
            2,
        )
        cv2.imshow("Capture Faces - press q to stop", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. Saved {saved} samples to {student_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture a face dataset for one student.")
    parser.add_argument("--id", type=int, required=True, help="Student's database id")
    parser.add_argument("--name", type=str, default="", help="Student's name (for logging only)")
    parser.add_argument("--samples", type=int, default=40, help="Number of samples to capture")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    args = parser.parse_args()

    if args.name:
        print(f"Capturing for: {args.name} (id={args.id})")
    capture(args.id, target_samples=args.samples, camera_index=args.camera)
