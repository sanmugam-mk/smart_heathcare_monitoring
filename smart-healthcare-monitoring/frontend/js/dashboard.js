import { api, jsonBody } from "./api.js";
import { getRole, requireSession, signOut } from "./auth.js";
import { updateCharts } from "./charts.js";
import { loadPatients } from "./patients.js";

if (requireSession()) {
  const errorBox = document.querySelector("#dashboard-error");
  const name = document.querySelector("#patient-name");
  const demographics = document.querySelector("#patient-demographics");
  const role = document.querySelector("#doctor-role");
  const isAdmin = getRole() === "Administrator";
  const waiting = document.querySelector("#waiting-message");
  let patientId = "";
  let timer = null;
  role.textContent = getRole();

  function showError(error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
  function clearError() { errorBox.hidden = true; }
  function updateRisk(risk) {
    const score = document.querySelector("#risk-score");
    const suffix = document.createElement("small");
    suffix.textContent = "/10";
    score.replaceChildren(document.createTextNode(String(risk?.RiskScore ?? "—")), suffix);
    const pill = document.querySelector("#risk-category");
    const category = risk?.Category || "Waiting for data";
    pill.textContent = category;
    pill.className = `risk-pill ${category === "NORMAL" ? "risk-normal" : category === "WARNING" ? "risk-warning" : category === "HIGH" ? "risk-high" : "risk-unknown"}`;
    const reasons = document.querySelector("#risk-reasons");
    reasons.replaceChildren();
    for (const reason of risk?.Reasons || ["Waiting for an AWS-stored reading."]) {
      const item = document.createElement("li");
      item.textContent = reason;
      reasons.append(item);
    }
  }
  function setLatest(reading) {
    waiting.hidden = Boolean(reading);
    for (const [id, value] of [["heart-rate", reading?.HeartRate], ["spo2", reading?.SpO2], ["temperature", reading?.Temperature]]) {
      document.getElementById(id).textContent = value === undefined ? "—" : String(value);
    }
    document.querySelector("#last-updated").textContent = reading ? new Date(reading.Timestamp).toLocaleString() : "—";
    const status = document.querySelector("#device-status");
    const fresh = reading && Date.now() - new Date(reading.Timestamp).getTime() <= 15000;
    status.className = `device-status ${fresh ? "device-online" : "device-offline"}`;
    status.lastChild.textContent = fresh ? "Device online" : reading ? "No recent device data" : "Waiting for device data";
  }
  function renderAlerts(alerts) {
    const list = document.querySelector("#alert-list");
    list.replaceChildren();
    if (!alerts.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = "No alerts recorded for this patient.";
      list.append(item);
      return;
    }
    for (const alert of alerts.slice(0, 8)) {
      const item = document.createElement("li");
      const severity = document.createElement("span");
      severity.className = "alert-severity";
      severity.textContent = `${alert.AlertType} · `;
      const description = document.createElement("span");
      description.textContent = `${alert.Message} (${alert.Status})`;
      item.append(severity, description);
      const nextStatus = alert.Status === "OPEN" ? "ACKNOWLEDGED"
        : alert.Status === "ACKNOWLEDGED" && isAdmin ? "RESOLVED" : null;
      if (nextStatus) {
        const action = document.createElement("button");
        action.className = "text-button";
        action.textContent = nextStatus === "ACKNOWLEDGED" ? "Acknowledge" : "Resolve";
        action.addEventListener("click", async () => {
          try {
            await api(`/alerts/${encodeURIComponent(alert.AlertId)}`, {
              method: "PATCH",
              body: jsonBody({ status: nextStatus }),
            });
            await refreshPatient();
          } catch (error) {
            showError(error);
          }
        });
        item.append(action);
      }
      list.append(item);
    }
  }

  async function refreshPatient() {
    if (!patientId) {
      setLatest(null);
      updateRisk(null);
      updateCharts([], []);
      return;
    }
    try {
      const [latest, history, risk, risks, alerts] = await Promise.all([
        api(`/patients/${encodeURIComponent(patientId)}/vitals/latest`),
        api(`/patients/${encodeURIComponent(patientId)}/vitals/history?limit=100`),
        api(`/patients/${encodeURIComponent(patientId)}/risk`),
        api(`/patients/${encodeURIComponent(patientId)}/risk/history?limit=100`),
        api(`/patients/${encodeURIComponent(patientId)}/alerts`),
      ]);
      clearError();
      setLatest(latest);
      updateRisk(risk);
      updateCharts(history || [], risks || []);
      renderAlerts(alerts || []);
      document.querySelector("#chart-updated").textContent = `Refreshed ${new Date().toLocaleTimeString()}`;
    } catch (error) {
      showError(error);
    }
  }

  document.addEventListener("patient-selected", (event) => {
    const patient = event.detail;
    patientId = patient?.PatientId || "";
    name.textContent = patient?.FullName || "Select a patient";
    demographics.textContent = patient
      ? `${patient.PatientId} · ${patient.Age} years · ${patient.Gender}`
      : "Register or select a patient to view monitoring data.";
    if (timer) clearInterval(timer);
    refreshPatient();
    if (patientId) timer = setInterval(refreshPatient, 5000);
  });
  document.querySelector("#refresh-alerts").addEventListener("click", refreshPatient);
  document.querySelector("#sign-out").addEventListener("click", signOut);
  loadPatients().catch(showError);
}
