# 🎯 TalentGraph — AI Recruiter Screening

Bulk-screen **PDF résumés** against **long job descriptions** with a LangGraph pipeline.
Ranked, explainable results; every run is persisted in MongoDB.

```
React (Vercel) ──HTTP──▶ FastAPI (Render) ──▶ LangGraph ──▶ Groq (gpt-oss-120b)
                              │
                              └──▶ MongoDB Atlas (batches + candidates)
```

## LangGraph workflow
`parse_resume → categorize_experience → assess_skillset → route →`
`schedule_hr_interview | escalate_to_recruiter | reject_application`

Routing rules (same as the original notebook): Match → shortlist; Senior but no match → escalate; otherwise reject.

## What changed vs. the notebook
| Notebook | This project |
|---|---|
| Plain-string input | PDF/TXT upload, text extraction, scanned-PDF detection |
| Hardcoded "Python Developer" | JD is parsed into structured requirements (must-have/nice-to-have, years, seniority) |
| Short JD only | Long JDs → chunked **map-reduce** extraction |
| LLM says "Match"/"No Match" (brittle string compare) | **Structured output** (Pydantic) → 0-100 score; match = score ≥ adjustable threshold |
| One candidate at a time | Up to 25 résumés, concurrent with a semaphore (respects Groq rate limits), background job + polling |
| No persistence | MongoDB: history, re-open, delete |
| print() output | Explainable UI: matched/missing skills, strengths, concerns, interview questions, rejection feedback |

## Run locally
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill GROQ_API_KEY + MONGODB_URI, then:
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload            # http://localhost:8000/docs

# frontend (new terminal)
cd frontend && npm install && cp .env.example .env && npm run dev   # http://localhost:5173
```

## Deploy

### 1. MongoDB Atlas (free)
1. Create an M0 cluster at cloud.mongodb.com.
2. **Database Access** → add a user + password.
3. **Network Access** → add `0.0.0.0/0` (Render free has no static IP).
4. **Connect → Drivers** → copy the URI, replace `<password>`. That is `MONGODB_URI`.

### 2. Backend on Render
1. Push this repo to GitHub.
2. Render → **New → Web Service** → pick the repo. (Or **New → Blueprint** to use `render.yaml`.)
3. Settings: **Root Directory** `backend` · **Build** `pip install -r requirements.txt` · **Start** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment variables**: `PYTHON_VERSION=3.12.8`, `GROQ_API_KEY`, `MONGODB_URI`, `CORS_ORIGINS=http://localhost:5173` (update in step 4).
5. Deploy; open `https://<name>.onrender.com/api/health` → `{"status":"ok","db":"up"}`.

### 3. Frontend on Vercel
1. Vercel → **Add New → Project** → import the same repo.
2. **Root Directory** `frontend` (framework auto-detects Vite; build `npm run build`, output `dist`).
3. **Environment variable**: `VITE_API_URL=https://<name>.onrender.com` (no trailing slash).
4. Deploy → you get `https://<project>.vercel.app`.

### 4. Connect them (CORS)
Render → your service → Environment → set
`CORS_ORIGINS=https://<project>.vercel.app` (comma-separate to keep localhost too) → it redeploys.
Vite env vars are baked in at build time, so if you change `VITE_API_URL`, redeploy Vercel.

### Gotchas
- Render free instances sleep after ~15 min idle; first request takes ~30-50 s. **Open the site once before your interview**, or ping `/api/health` with a free uptime monitor.
- Free Render restarts can interrupt a running batch; the UI will show it stuck at "screening". For production you'd move to a queue (Celery/RQ) or Render background worker.
- Scanned (image-only) PDFs are rejected with a clear message; adding OCR (Tesseract) is a natural extension.
- Groq free tier has rate limits: tune `LLM_CONCURRENCY` (default 3).

## Interview talking points
- **Why LangGraph?** Explicit state machine, conditional edges, each node testable in isolation; easy to add human-in-the-loop on the "escalate" branch.
- **Why structured output?** Eliminates string-parsing failures (the notebook's `"Match"` comparison and `*` stripping hack).
- **Why map-reduce for JDs?** Bounded context per call, parallelizable, scales to arbitrarily long JDs.
- **Why background tasks + polling?** Screening 25 résumés takes minutes; HTTP requests would time out. Returns `202` + batch id.
- **Bias/fairness:** the prompt scores only on evidenced skills and experience, never on name/gender/age; a human reviews the escalate branch. Mention audit trail in MongoDB.
- **Next steps:** OCR, embeddings pre-filter for 1000s of résumés, auth, queue/worker, email integration, LangSmith tracing.
