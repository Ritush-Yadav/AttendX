/* Loading screen, mobile sidebar toggle, and the shared student profile modal. */

(function () {
  const MIN_LOADER_MS = 700;
  const MAX_LOADER_MS = 3500; // hide even if a slow/blocked CDN asset never finishes
  const start = Date.now();
  let hidden = false;

  function hideLoader() {
    if (hidden) return;
    hidden = true;
    document.body.classList.remove("pre-load");
  }

  window.addEventListener("load", () => {
    const elapsed = Date.now() - start;
    const wait = Math.max(MIN_LOADER_MS - elapsed, 0);
    setTimeout(hideLoader, wait);
  });
  setTimeout(hideLoader, MAX_LOADER_MS);

  const hamburger = document.getElementById("hamburger");
  const sidebar = document.getElementById("sidebar");
  if (hamburger && sidebar) {
    hamburger.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (e) => {
      if (
        sidebar.classList.contains("open") &&
        !sidebar.contains(e.target) &&
        !hamburger.contains(e.target)
      ) {
        sidebar.classList.remove("open");
      }
    });
  }

  // ---- Student profile modal -------------------------------------------
  const modal = document.getElementById("student-modal");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");

  function closeStudentModal() {
    if (modal) modal.classList.add("hidden");
  }

  async function openStudentModal(studentId) {
    if (!modal || !modalBody) return;
    modalBody.innerHTML = `<p class="muted small">Loading profile&hellip;</p>`;
    modal.classList.remove("hidden");

    try {
      const res = await fetch(`/api/student/${studentId}`);
      const data = await res.json();
      if (!data.ok) {
        modalBody.innerHTML = `<p class="muted small">${data.message || "Could not load student."}</p>`;
        return;
      }

      const s = data.student;
      const historyHtml = data.history.length
        ? data.history
            .map(
              (h) => `
              <div class="profile-history-item">
                <span class="mono">${h.date} &middot; ${h.time}</span>
                <span class="mono">${h.confidence != null ? h.confidence.toFixed(1) : "&mdash;"}</span>
              </div>`
            )
            .join("")
        : `<p class="muted small">No attendance recorded yet.</p>`;

      modalBody.innerHTML = `
        <div class="profile-head">
          <div class="row-avatar large">${s.name.charAt(0).toUpperCase()}</div>
          <div>
            <h3>${s.name}</h3>
            <p class="mono muted small">${s.roll_no} &middot; ${s.department || "No department"}</p>
          </div>
        </div>
        <div class="profile-stats">
          <div class="profile-stat"><span>Total days present</span><strong>${data.total_present}</strong></div>
          <div class="profile-stat"><span>Dataset samples</span><strong>${s.samples_captured}</strong></div>
        </div>
        <h3 style="font-size:0.85rem;margin-bottom:8px;">Recent attendance</h3>
        <div>${historyHtml}</div>
      `;
    } catch (err) {
      modalBody.innerHTML = `<p class="muted small">Something went wrong loading this profile.</p>`;
    }
  }

  if (modalClose) modalClose.addEventListener("click", closeStudentModal);
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeStudentModal();
    });
  }

  document.querySelectorAll(".clickable-row[data-student-id]").forEach((row) => {
    row.addEventListener("click", () => openStudentModal(row.dataset.studentId));
  });

  window.openStudentModal = openStudentModal;
  window.closeStudentModal = closeStudentModal;
})();
