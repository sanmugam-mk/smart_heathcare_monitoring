import { api, jsonBody } from "./api.js";

const list = document.querySelector("#patient-list");
const search = document.querySelector("#patient-search");
const form = document.querySelector("#patient-form");
const feedback = document.querySelector("#patient-feedback");
let patients = [];
let selectedPatientId = "";

function renderPatients() {
  const term = search.value.trim().toLowerCase();
  const shown = patients.filter((patient) =>
    `${patient.PatientId} ${patient.FullName}`.toLowerCase().includes(term));
  list.replaceChildren();
  if (!shown.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = patients.length ? "No patients match your search." : "No patients are registered yet.";
    list.append(empty);
    return;
  }
  for (const patient of shown) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `patient-item${patient.PatientId === selectedPatientId ? " active" : ""}`;
    button.innerHTML = `<span><strong></strong><small></small></span><span aria-hidden="true">›</span>`;
    button.querySelector("strong").textContent = patient.FullName;
    button.querySelector("small").textContent = `${patient.PatientId} · ${patient.Age} years`;
    button.addEventListener("click", () => {
      selectedPatientId = patient.PatientId;
      renderPatients();
      document.dispatchEvent(new CustomEvent("patient-selected", { detail: patient }));
    });
    list.append(button);
  }
}

export async function loadPatients() {
  list.textContent = "Loading patients from AWS…";
  try {
    patients = await api("/patients") || [];
    renderPatients();
    const patient = patients.find((item) => item.PatientId === selectedPatientId) || patients[0];
    if (patient) {
      selectedPatientId = patient.PatientId;
      renderPatients();
      document.dispatchEvent(new CustomEvent("patient-selected", { detail: patient }));
    } else {
      selectedPatientId = "";
      document.dispatchEvent(new CustomEvent("patient-selected", { detail: null }));
    }
  } catch (error) {
    list.textContent = error.message;
    throw error;
  }
}

search.addEventListener("input", renderPatients);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.textContent = "";
  const data = new FormData(form);
  const patient = {
    PatientId: data.get("PatientId").trim(),
    FullName: data.get("FullName").trim(),
    Age: Number(data.get("Age")),
    Gender: data.get("Gender"),
  };
  try {
    await api("/patients", { method: "POST", body: jsonBody(patient) });
    feedback.textContent = "Patient registered.";
    form.reset();
    form.elements.PatientId.value = patient.PatientId;
    await loadPatients();
  } catch (error) {
    feedback.textContent = error.message;
  }
});

document.querySelector("#refresh-patients").addEventListener("click", () => loadPatients().catch(() => {}));
