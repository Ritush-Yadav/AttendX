"""
face_utils.py

Shared face-detection helpers used by app.py, capture_faces.py and train_model.py.
"""

import base64
import os
import re
import cv2
import numpy as np

FACE_SIZE = (200, 200)
_cascade = None


def get_face_cascade():
    """Load OpenCV Haar Cascade safely."""

    global _cascade

    if _cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

        if not os.path.exists(cascade_path):
            raise FileNotFoundError(
                f"Haar Cascade file not found:\n{cascade_path}"
            )

        _cascade = cv2.CascadeClassifier(cascade_path)

        if _cascade.empty():
            raise RuntimeError(
                f"Failed to load Haar Cascade:\n{cascade_path}"
            )

    return _cascade


def detect_largest_face(gray_frame):
    """
    Detect the largest face in a grayscale frame.
    Returns (x, y, w, h) or None.
    """

    if gray_frame is None or gray_frame.size == 0:
        return None

    cascade = get_face_cascade()

    faces = cascade.detectMultiScale(
        gray_frame,
        scaleFactor=1.15,
        minNeighbors=6,
        minSize=(90, 90)
    )

    if len(faces) == 0:
        return None

    return max(faces, key=lambda f: f[2] * f[3])


def crop_and_normalize(gray_frame, box):
    """Crop and normalize face image."""

    x, y, w, h = box
    face = gray_frame[y:y+h, x:x+w]
    face = cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_LINEAR)
    face = cv2.equalizeHist(face)
    return face


def decode_base64_image(data_url):
    """
    Decode browser base64 image into OpenCV BGR frame.
    """

    match = re.match(r"^data:image/\w+;base64,(.*)$", data_url)
    b64_data = match.group(1) if match else data_url

    img_bytes = base64.b64decode(b64_data)
    np_arr = np.frombuffer(img_bytes, dtype=np.uint8)

    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return frame


def student_dataset_dir(dataset_root, student_id):
    path = os.path.join(dataset_root, str(student_id))
    os.makedirs(path, exist_ok=True)
    return path


def next_sample_index(student_dir):
    existing = [f for f in os.listdir(student_dir) if f.endswith(".jpg")]
    return len(existing) + 1