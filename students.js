/* Add-student modal + delete-student flow on the Students page. */

const addModal = document.getElementById("add-student-modal");
const openAddBtn = document.getElementById("open-add-student");
const addForm = document.getElementById("add-student-form");

function openAddStudentModal() {
  addModal.classList.remove("hidden");
}
function closeAddStudentModal() {
  addModal.classList.add("hidden");
  addForm.reset();
}

if (openAddBtn) openAddBtn.addEventListener("click", openAddStudentModal);
if (window.location.hash === "#add") openAddStudentModal();
if (addModal) {
  addModal.addEventListener("click", (e) => {
    if (e.target === addModal) closeAddStudentModal();
  });
}

if (addForm) {
  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(addForm);
    const submitBtn = addForm.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "Saving\u2026";

    try {
      const res = await fetch("/students/add", { method: "POST", body: formData });
      const data = await res.json();
      if (!data.ok) {
        showToast("error", "Could not add student", data.message);
        submitBtn.disabled = false;
        submitBtn.textContent = "Save & capture faces";
        return;
      }
      showToast("success", "Student added", "Redirecting to face capture\u2026");
      setTimeout(() => {
        window.location.href = `/capture/${data.student_id}`;
      }, 500);
    } catch (err) {
      showToast("error", "Network error", "Could not reach the server.");
      submitBtn.disabled = false;
      submitBtn.textContent = "Save & capture faces";
    }
  });
}

async function deleteStudent(id, name) {
  if (!confirm(`Delete ${name}? This removes their face dataset and attendance history.`)) return;
  try {
    const res = await fetch(`/students/delete/${id}`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      showToast("success", "Student removed", `${name} was deleted.`);
      setTimeout(() => window.location.reload(), 500);
    } else {
      showToast("error", "Delete failed", data.message || "");
    }
  } catch (err) {
    showToast("error", "Network error", "Could not reach the server.");
  }
}

window.deleteStudent = deleteStudent;
window.closeAddStudentModal = closeAddStudentModal;
