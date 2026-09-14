"""
train_model.py

Trains an LBPH (Local Binary Patterns Histogram) face recognizer from every
student folder under dataset/, and writes the result to trainer/trainer.yml.

Can be run directly:
    python train_model.py

Or imported and called from the web app after a capture session:
    from train_model import train
    result = train()
"""

import os
import sqlite3

import cv2
import numpy as np

BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAINER_DIR = os.path.join(BASE_DIR, "trainer")
TRAINER_PATH = os.path.join(TRAINER_DIR, "trainer.yml")
DB_PATH = os.path.join(BASE_DIR, "database.db")


def _mark_trained(student_ids):
    if not student_ids:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE students SET trained = 0")
    qmarks = ",".join("?" * len(student_ids))
    conn.execute(f"UPDATE students SET trained = 1 WHERE id IN ({qmarks})", student_ids)
    conn.commit()
    conn.close()


def train():
    """
    Walk dataset/<student_id>/*.jpg, train an LBPH recognizer, and persist it.
    Returns a dict summary: {ok, students_trained, samples_used, message}.
    """
    os.makedirs(TRAINER_DIR, exist_ok=True)

    if not os.path.isdir(DATASET_DIR):
        return {"ok": False, "students_trained": 0, "samples_used": 0,
                "message": "No dataset directory found."}

    faces = []
    labels = []
    student_ids = []

    for entry in sorted(os.listdir(DATASET_DIR)):
        student_dir = os.path.join(DATASET_DIR, entry)
        if not os.path.isdir(student_dir) or not entry.isdigit():
            continue

        student_id = int(entry)
        sample_count = 0
        for fname in os.listdir(student_dir):
            if not fname.lower().endswith(".jpg"):
                continue
            img_path = os.path.join(student_dir, fname)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            faces.append(img)
            labels.append(student_id)
            sample_count += 1

        if sample_count > 0:
            student_ids.append(student_id)

    if not faces:
        return {"ok": False, "students_trained": 0, "samples_used": 0,
                "message": "No face samples found. Capture at least one student first."}

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))
    recognizer.write(TRAINER_PATH)

    _mark_trained(student_ids)

    return {
        "ok": True,
        "students_trained": len(student_ids),
        "samples_used": len(faces),
        "message": f"Trained on {len(faces)} samples across {len(student_ids)} student(s).",
    }


if __name__ == "__main__":
    result = train()
    print(result["message"])
