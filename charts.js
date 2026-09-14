/* Populates dashboard stat cards and renders the trend / department charts.
   Stat cards never depend on Chart.js — if that CDN is slow or blocked,
   the numbers should still show up. */

(function () {
  const CHART_TEXT = "#8b9aae";
  const CHART_GRID = "rgba(255,255,255,0.06)";
  const hasChart = typeof Chart !== "undefined";

  if (hasChart) {
    Chart.defaults.font.family = "'Space Grotesk', sans-serif";
    Chart.defaults.color = CHART_TEXT;
  }

  async function loadStats() {
    const res = await fetch("/api/stats");
    const data = await res.json();
    document.getElementById("stat-total").textContent = data.total_students;
    document.getElementById("stat-present").textContent = data.present_today;
    document.getElementById("stat-absent").textContent = data.absent_today;
    document.getElementById("stat-trained").textContent = data.trained_students;
    document.getElementById("stat-rate").textContent = `${data.attendance_rate}% attendance rate`;
  }

  async function loadTrend() {
    const res = await fetch("/api/attendance-trend");
    const data = await res.json();
    if (!hasChart) return;
    const ctx = document.getElementById("trendChart");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Students present",
            data: data.values,
            borderColor: "#22d3b6",
            backgroundColor: "rgba(34,211,182,0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointBackgroundColor: "#22d3b6",
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: CHART_GRID } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  const DEPT_COLORS = ["#38bdf8", "#34d399", "#a78bfa", "#fbbf24", "#fb7185", "#22d3b6"];

  async function loadDeptBreakdown() {
    const res = await fetch("/api/department-breakdown");
    const data = await res.json();
    const total = data.values.reduce((a, b) => a + b, 0);
    document.getElementById("donut-total").textContent = total;

    const legend = document.getElementById("dept-legend");
    legend.innerHTML = data.labels
      .map(
        (label, i) => `
        <div class="dept-legend-item">
          <span class="dept-legend-dot" style="background:${DEPT_COLORS[i % DEPT_COLORS.length]}"></span>
          <span class="dept-name">${label}</span>
          <strong>${data.values[i]}</strong>
        </div>`
      )
      .join("") || `<p class="muted small">No departments yet.</p>`;

    if (!hasChart) return;
    const ctx = document.getElementById("deptChart");
    new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: data.labels,
        datasets: [
          {
            data: data.values,
            backgroundColor: DEPT_COLORS,
            borderColor: "#10151d",
            borderWidth: 3,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        cutout: "72%",
      },
    });
  }

  loadStats();
  loadTrend();
  loadDeptBreakdown();
})();
