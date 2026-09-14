/* Runs the live attendance scanner: streams the webcam, polls /api/recognize,
   and drops a card into the "recognized just now" feed on every new match. */

const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const octx = overlay.getContext("2d");
const statusEl = document.getElementById("cam-status");
const sweep = document.getElementById("scan-sweep");
const startBtn = document.getElementById("start-scan");
const stopBtn = document.getElementById("stop-scan");
const feed = document.getElementById("recent-feed");

const sendCanvas = document.createElement("canvas");
const sctx = sendCanvas.getContext("2d");

let stream = null;
let scanTimer = null;
let inFlight = false;
const markedThisSession = new Set();

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
  } catch (err) {
    statusEl.textContent = "Camera access denied";
    showToast("error", "Camera unavailable", "Allow camera access to scan attendance.");
  }
}

function drawBox(box, color) {
  octx.clearRect(0, 0, overlay.width, overlay.height);
  if (!box) return;
  const scaleX = overlay.width / video.videoWidth;
  const scaleY = overlay.height / video.videoHeight;
  octx.strokeStyle = color;
  octx.lineWidth = 2;
  octx.shadowColor = color;
  octx.shadowBlur = 8;
  octx.strokeRect(box.x * scaleX, box.y * scaleY, box.w * scaleX, box.h * scaleY);
}

function addFeedItem(student, time, badgeText, badgeClass) {
  const empty = feed.querySelector(".muted");
  if (empty) empty.remove();

  const item = document.createElement("div");
  item.className = "feed-item";
  item.innerHTML = `
    <div class="row-avatar">${student.name.charAt(0).toUpperCase()}</div>
    <div>
      <strong>${student.name}</strong>
      <span class="mono">${student.roll_no} &middot; ${time}</span>
    </div>
    <span class="badge ${badgeClass}">${badgeText}</span>
  `;
  feed.prepend(item);
}

async function scanFrame() {
  if (inFlight || !video.videoWidth) return;
  inFlight = true;

  sendCanvas.width = video.videoWidth;
  sendCanvas.height = video.videoHeight;
  sctx.drawImage(video, 0, 0, sendCanvas.width, sendCanvas.height);
  const imageData = sendCanvas.toDataURL("image/jpeg", 0.82);

  try {
    const res = await fetch("/api/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: imageData }),
    });
    const data = await res.json();

    if (!data.ok) {
      statusEl.textContent = data.message || "Model not trained yet";
      statusEl.className = "cam-status status-warn";
      return;
    }
    if (!data.face_found) {
      drawBox(null);
      statusEl.textContent = "Scanning for a face\u2026";
      statusEl.className = "cam-status";
      return;
    }
    if (!data.recognized) {
      drawBox(data.box, "#fbbf24");
      statusEl.textContent = "Face not recognized";
      statusEl.className = "cam-status status-warn";
      return;
    }

    drawBox(data.box, "#34d399");
    statusEl.textContent = `Matched: ${data.student.name}`;
    statusEl.className = "cam-status status-good";

    const key = `${data.student.id}`;
    if (!data.already_marked && !markedThisSession.has(key)) {
      markedThisSession.add(key);
      addFeedItem(data.student, data.time, "Marked", "badge-green");
      showToast("success", "Attendance marked", `${data.student.name} (${data.student.roll_no})`);
    } else if (!markedThisSession.has(key)) {
      markedThisSession.add(key);
      addFeedItem(data.student, data.time, "Already in", "badge-teal");
    }
  } catch (err) {
    statusEl.textContent = "Connection error";
  } finally {
    inFlight = false;
  }
}

function startScan() {
  startBtn.disabled = true;
  stopBtn.disabled = false;
  sweep.classList.add("active");
  statusEl.textContent = "Scanning\u2026";
  scanTimer = setInterval(scanFrame, 700);
}

function stopScan() {
  startBtn.disabled = false;
  stopBtn.disabled = true;
  sweep.classList.remove("active");
  clearInterval(scanTimer);
  scanTimer = null;
  drawBox(null);
  statusEl.textContent = "Scanner idle";
  statusEl.className = "cam-status";
}

startBtn.addEventListener("click", async () => {
  if (!stream) await startCamera();
  startScan();
});
stopBtn.addEventListener("click", stopScan);

startCamera();
