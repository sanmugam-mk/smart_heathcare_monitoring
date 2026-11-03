import { api, jsonBody } from "./api.js";
import { requireSession, signOut } from "./auth.js";

if (requireSession()) {
  const patientInput = document.querySelector("#document-patient-id");
  const fileInput = document.querySelector("#document-file");
  const list = document.querySelector("#document-list");
  const feedback = document.querySelector("#upload-feedback");
  const errorBox = document.querySelector("#document-error");

  async function loadDocuments() {
    errorBox.hidden = true;
    const patientId = patientInput.value.trim();
    if (!patientId) {
      list.textContent = "Enter a patient ID to load documents.";
      return;
    }
    try {
      const documents = await api(`/documents?patientId=${encodeURIComponent(patientId)}`) || [];
      list.replaceChildren();
      if (!documents.length) {
        list.textContent = "No documents found for this patient.";
        return;
      }
      for (const documentRecord of documents) {
        const row = document.createElement("div");
        row.className = "document-row";
        const details = document.createElement("span");
        const title = document.createElement("strong");
        const meta = document.createElement("small");
        title.textContent = documentRecord.FileName;
        meta.textContent = `${documentRecord.ContentType} · ${documentRecord.SizeBytes} bytes · ${new Date(documentRecord.CreatedAt).toLocaleString()}`;
        details.append(title, meta);
        const download = document.createElement("button");
        download.className = "button button-outline";
        download.textContent = "Secure download";
        download.addEventListener("click", async () => {
          try {
            const result = await api(`/documents/${encodeURIComponent(documentRecord.DocumentId)}/download-url?patientId=${encodeURIComponent(patientId)}`);
            window.location.assign(result.downloadUrl);
          } catch (error) { showError(error); }
        });
        row.append(details, download);
        list.append(row);
      }
    } catch (error) {
      showError(error);
    }
  }
  function showError(error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }

  document.querySelector("#upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    feedback.textContent = "";
    const file = fileInput.files?.[0];
    const patientId = patientInput.value.trim();
    if (!file) return;
    if (!["application/pdf", "image/jpeg", "image/png"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      showError(new Error("Choose a PDF, JPEG, or PNG file no larger than 10 MB."));
      return;
    }
    try {
      const result = await api("/documents/upload-url", {
        method: "POST",
        body: jsonBody({ patientId, fileName: file.name, contentType: file.type, sizeBytes: file.size }),
      });
      const formData = new FormData();
      for (const [key, value] of Object.entries(result.upload.fields)) formData.append(key, value);
      formData.append("file", file);
      const upload = await fetch(result.upload.url, {
        method: "POST",
        body: formData,
      });
      if (!upload.ok) throw new Error(`S3 upload failed (${upload.status}). Request a new upload link and try again.`);
      await api(`/documents/${encodeURIComponent(result.document.DocumentId)}/complete`, {
        method: "POST",
        body: jsonBody({ patientId }),
      });
      feedback.textContent = "Document uploaded to private S3 storage.";
      fileInput.value = "";
      await loadDocuments();
    } catch (error) {
      showError(error);
    }
  });
  document.querySelector("#refresh-documents").addEventListener("click", loadDocuments);
  document.querySelector("#sign-out").addEventListener("click", signOut);
  patientInput.addEventListener("change", loadDocuments);
  loadDocuments();
}
