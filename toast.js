/* Lightweight toast notifications — no external dependency. */

function showToast(type, title, message, duration = 4200) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = {
    success: "&#10003;",
    error: "&#10005;",
    warn: "&#33;",
    info: "&#8505;",
  };

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div>
      <strong>${title}</strong>
      ${message ? `<span>${message}</span>` : ""}
    </div>
  `;
  container.appendChild(toast);

  const remove = () => {
    toast.classList.add("toast-out");
    setTimeout(() => toast.remove(), 250);
  };

  setTimeout(remove, duration);
  toast.addEventListener("click", remove);
}

window.showToast = showToast;
