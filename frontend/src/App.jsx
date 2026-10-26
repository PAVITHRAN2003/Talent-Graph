import { useEffect, useRef, useState } from "react";
import { createBatch, getBatch, listBatches, deleteBatch } from "./api";

const DECISION = {
  shortlist: { label: "Shortlisted", cls: "green" },
  escalate: { label: "Escalated to recruiter", cls: "amber" },
  reject: { label: "Rejected", cls: "red" },
};

function Ring({ score }) {
  const r = 22, c = 2 * Math.PI * r;
  const color = score >= 70 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f87171";
  return (
    <svg width="56" height="56" viewBox="0 0 56 56">
      <circle cx="28" cy="28" r={r} fill="none" stroke="#243049" strokeWidth="5" />
      <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c - (c * score) / 100} transform="rotate(-90 28 28)" />
      <text x="28" y="33" textAnchor="middle" fontSize="15" fontWeight="700" fill="#e6edf7">{score}</text>
    </svg>
  );
}

const Chips = ({ items, cls }) => (
  <div className="chips">{(items || []).map((s) => <span key={s} className={`chip ${cls || ""}`}>{s}</span>)}</div>
);

function Candidate({ c, open, onToggle }) {
  if (c.status === "error")
    return (
      <div className="cand err">
        <div className="cand-head"><div className="grow"><b>{c.filename}</b><div className="muted">⚠ {c.error}</div></div></div>
      </div>
    );
  const d = DECISION[c.decision];
  return (
    <div className="cand">
      <div className="cand-head" onClick={onToggle}>
        <Ring score={c.score} />
        <div className="grow">
          <b>{c.name}</b> <span className="muted">· {c.current_title || "—"} · {c.years_experience}y · {c.experience_level}</span>
          <div className="muted small">{c.filename}</div>
        </div>
        <span className={`badge ${d.cls}`}>{d.label}</span>
      </div>
      {open && (
        <div className="cand-body">
          <p>{c.reasoning}</p>
          <div className="cols">
            <div><h4>Matched skills</h4><Chips items={c.matched_skills} cls="ok" /></div>
            <div><h4>Missing skills</h4><Chips items={c.missing_skills} cls="bad" /></div>
          </div>
          <div className="cols">
            <div><h4>Strengths</h4><ul>{c.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>
            <div><h4>Concerns</h4><ul>{c.concerns.map((s) => <li key={s}>{s}</li>)}</ul></div>
          </div>
          {c.interview_questions?.length > 0 && (
            <><h4>Suggested interview questions</h4><ol>{c.interview_questions.map((q) => <li key={q}>{q}</li>)}</ol></>
          )}
          {c.feedback && <><h4>Candidate feedback (draft)</h4><p className="muted">{c.feedback}</p></>}
          <div className="muted small">{c.email}</div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [threshold, setThreshold] = useState(70);
  const [batch, setBatch] = useState(null);
  const [history, setHistory] = useState([]);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const jdInput = useRef(), resInput = useRef();

  const refreshHistory = () => listBatches().then(setHistory).catch(() => {});
  useEffect(() => { refreshHistory(); }, []);

  // poll while a batch is running
  useEffect(() => {
    if (!batch || ["done", "failed"].includes(batch.status)) return;
    const t = setInterval(async () => {
      try {
        const b = await getBatch(batch.id);
        setBatch(b);
        if (["done", "failed"].includes(b.status)) refreshHistory();
      } catch {}
    }, 2000);
    return () => clearInterval(t);
  }, [batch?.id, batch?.status]);

  const addResumes = (fileList) => {
    const incoming = Array.from(fileList);   // copy now, before the input gets reset
    const ok = incoming.filter((f) => /\.(pdf|txt)$/i.test(f.name));
    setError(ok.length < incoming.length
      ? `Only PDF or TXT files are supported. Skipped ${incoming.length - ok.length} file(s).`
      : "");
    setResumes((prev) => [...prev, ...ok].slice(0, 25));
  };

  const start = async () => {
    setError(""); setBusy(true);
    try {
      const { batch_id } = await createBatch({ jdText, jdFile, resumes, threshold });
      setBatch(await getBatch(batch_id)); setOpen(null);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const remove = async (id) => {
    await deleteBatch(id);
    if (batch?.id === id) setBatch(null);
    refreshHistory();
  };

  const cands = batch?.candidates || [];
  const count = (d) => cands.filter((c) => c.decision === d).length;
  const running = batch && !["done", "failed"].includes(batch.status);
  const canStart = !busy && resumes.length > 0 && (jdFile || jdText.trim().length >= 50);

  return (
    <div className="app">
      <header>
        <h1>🎯 TalentGraph</h1>
        <p className="muted">AI recruiter screening — bulk PDF résumés vs. long job descriptions, orchestrated with LangGraph.</p>
        <div className="pipeline">
          {["Parse résumé", "Categorize experience", "Assess skills", "Route decision"].map((s, i) => (
            <span key={s}>{i > 0 && <i>→</i>}<b>{s}</b></span>
          ))}
          <i>→</i><b className="green">Shortlist</b><i>/</i><b className="amber">Escalate</b><i>/</i><b className="red">Reject</b>
        </div>
      </header>

      <main>
        <section className="panel">
          <h3>1 · Job description</h3>
          <textarea placeholder="Paste a job description (any length)…" value={jdText}
            onChange={(e) => setJdText(e.target.value)} disabled={!!jdFile} />
          <div className="row">
            <button className="ghost" onClick={() => jdInput.current.click()}>📄 {jdFile ? jdFile.name : "…or upload JD PDF"}</button>
            {jdFile && <button className="ghost" onClick={() => setJdFile(null)}>✕</button>}
            <input ref={jdInput} type="file" accept=".pdf,.txt" hidden onChange={(e) => setJdFile(e.target.files[0] || null)} />
          </div>

          <h3>2 · Résumés <span className="muted small">(PDF/TXT, up to 25)</span></h3>
          <div className={`drop ${drag ? "drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); addResumes(e.dataTransfer.files); }}
            onClick={() => resInput.current.click()}>
            Drag & drop résumés here, or click to browse
            <input ref={resInput} type="file" accept=".pdf,.txt" multiple hidden
              onChange={(e) => { addResumes(e.target.files); e.target.value = ""; }} />
          </div>
          {resumes.length > 0 && (
            <ul className="files">
              {resumes.map((f, i) => (
                <li key={i}>{f.name}<button onClick={() => setResumes(resumes.filter((_, j) => j !== i))}>✕</button></li>
              ))}
            </ul>
          )}

          <h3>3 · Match threshold: <span className="accent">{threshold}</span></h3>
          <input type="range" min="40" max="95" value={threshold} onChange={(e) => setThreshold(+e.target.value)} />

          {error && <div className="error">{error}</div>}
          <button className="primary" disabled={!canStart} onClick={start}>
            {busy ? "Uploading…" : `Screen ${resumes.length || ""} candidate${resumes.length === 1 ? "" : "s"}`}
          </button>

          {history.length > 0 && (
            <>
              <h3>History</h3>
              <ul className="history">
                {history.map((h) => (
                  <li key={h.id}>
                    <span onClick={() => getBatch(h.id).then(setBatch)}>
                      <b>{h.title}</b><br /><span className="muted small">{h.total} résumés · {h.status} · {new Date(h.created_at + "Z").toLocaleString()}</span>
                    </span>
                    <button onClick={() => remove(h.id)}>🗑</button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="results">
          {!batch ? (
            <div className="empty">Upload a JD and résumés to see a ranked, explainable shortlist.</div>
          ) : (
            <>
              <div className="panel">
                <div className="row between">
                  <h2>{batch.jd?.title || "Analyzing job description…"}</h2>
                  <span className={`badge ${batch.status === "done" ? "green" : batch.status === "failed" ? "red" : "amber"}`}>{batch.status}</span>
                </div>
                {batch.status === "failed" && <div className="error">{batch.error}</div>}
                {running && (
                  <div className="bar"><div style={{ width: `${(batch.completed / batch.total) * 100}%` }} /></div>
                )}
                {running && <div className="muted small">{batch.completed}/{batch.total} screened</div>}
                {batch.jd && (
                  <>
                    <div className="muted small">Required: {batch.jd.min_years_experience}+ yrs · {batch.jd.seniority} · JD size {batch.jd_chars?.toLocaleString()} chars</div>
                    <h4>Must-have</h4><Chips items={batch.jd.must_have_skills} />
                    <h4>Nice-to-have</h4><Chips items={batch.jd.nice_to_have_skills} cls="dim" />
                  </>
                )}
                <div className="stats">
                  <div><b className="green">{count("shortlist")}</b>Shortlisted</div>
                  <div><b className="amber">{count("escalate")}</b>Escalated</div>
                  <div><b className="red">{count("reject")}</b>Rejected</div>
                </div>
              </div>
              {cands.map((c, i) => (
                <Candidate key={c.id} c={c} open={open === c.id} onToggle={() => setOpen(open === c.id ? null : c.id)} />
              ))}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
