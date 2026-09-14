/* Drives the enrollment webcam: streams video, periodically posts frames to
   /api/capture/<id>, and reflects progress/box detection back onto the UI. */

const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const octx = overlay.getContext("2d");
const statusEl = document.getElementById("cam-status");
const sweep = document.querySelector(".scan-sweep");
const startBtn = document.getElementById("start-capture");
const stopBtn = document.getElementById("stop-capture");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");
const trainBtn = document.getElementById("train-btn");

const sendCanvas = document.createElement("canvas");
const sctx = sendCanvas.getContext("2d");

let stream = null;
let captureTimer = null;
let inFlight = false;
let savedCount = parseInt(progressText.textContent.split("/")[0], 10) || 0;

function sizeOverlay() {
  overlay.width = video.clientWidth;
  overlay.height = video.clientHeight;
}
window.addEventListener("resize", sizeOverlay);

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    video.srcObject = stream;
    await video.play();
    sizeOverlay();
    statusEl.textContent = "Camera ready";
  } catch (err) {
    statusEl.textContent = "Camera access denied";
    showToast("error", "Camera unavailable", "Allow camera access to capture faces.");
  }
}

function drawBox(box) {
  octx.clearRect(0, 0, overlay.width, overlay.height);
  if (!box) return;
  const scaleX = overlay.width / video.videoWidth;
  const scaleY = overlay.height / video.videoHeight;
  octx.strokeStyle = "#22d3b6";
  octx.lineWidth = 2;
  octx.shadowColor = "#22d3b6";
  octx.shadowBlur = 8;
  octx.strokeRect(box.x * scaleX, box.y * scaleY, box.w * scaleX, box.h * scaleY);
}

async function captureFrame() {
  if (inFlight || !video.videoWidth) return;
  inFlight = true;

  sendCanvas.width = video.videoWidth;
  sendCanvas.height = video.videoHeight;
  sctx.drawImage(video, 0, 0, sendCanvas.width, sendCanvas.height);
  const imageData = sendCanvas.toDataURL("image/jpeg", 0.82);

  try {
    const res = await fetch(`/api/capture/${STUDENT_ID}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: imageData }),
    });
    const data = await res.json();

    if (!data.face_found) {
      drawBox(null);
      statusEl.textContent = "No face detected — center your face";
      statusEl.className = "cam-status status-warn";
    } else {
      drawBox(data.box);
      savedCount = data.saved;
      progressText.textContent = `${savedCount}/${TARGET_SAMPLES}`;
      progressBar.style.width = `${Math.min((savedCount / TARGET_SAMPLES) * 100, 100)}%`;
      statusEl.textContent = "Face captured";
      statusEl.className = "cam-status status-good";

      if (data.complete) {
        stopCapture();
        trainBtn.disabled = false;
        showToast("success", "Capture complete", `${savedCount} samples saved. Ready to train.`);
      }
    }
  } catch (err) {
    statusEl.textContent = "Connection error";
  } finally {
    inFlight = false;
  }
}

function startCapture() {
  startBtn.disabled = true;
  stopBtn.disabled = false;
  sweep.classList.add("active");
  captureTimer = setInterval(captureFrame, 380);
}

function stopCapture() {
  startBtn.disabled = false;
  stopBtn.disabled = true;
  sweep.classList.remove("active");
  clearInterval(captureTimer);
  captureTimer = null;
  drawBox(null);
}

startBtn.addEventListener("click", async () => {
  if (!stream) await startCamera();
  startCapture();
});
stopBtn.addEventListener("click", stopCapture);

trainBtn.addEventListener("click", async () => {
  trainBtn.disabled = true;
  trainBtn.textContent = "Training\u2026";
  try {
    const res = await fetch("/api/train", { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      showToast("success", "Model trained", data.message);
    } else {
      showToast("warn", "Training incomplete", data.message);
    }
  } catch (err) {
    showToast("error", "Training failed", "Could not reach the server.");
  } finally {
    trainBtn.textContent = "Train Recognition Model";
    trainBtn.disabled = savedCount < TARGET_SAMPLES;
  }
});

startCamera();
