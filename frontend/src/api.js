const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function j(res) {
  if (!res.ok) {
    let msg = res.statusText;
    try { const b = await res.json(); msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

export const createBatch = ({ jdText, jdFile, resumes, threshold }) => {
  const f = new FormData();
  f.append("jd_text", jdText || "");
  f.append("threshold", String(threshold));
  if (jdFile) f.append("jd_file", jdFile);
  resumes.forEach((r) => f.append("resumes", r));
  return fetch(`${BASE}/api/batches`, { method: "POST", body: f }).then(j);
};
export const getBatch = (id) => fetch(`${BASE}/api/batches/${id}`).then(j);
export const listBatches = () => fetch(`${BASE}/api/batches`).then(j);
export const deleteBatch = (id) => fetch(`${BASE}/api/batches/${id}`, { method: "DELETE" }).then(j);
