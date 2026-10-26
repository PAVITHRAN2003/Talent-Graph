import asyncio
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from . import config
from .db import get_db
from .graph import screen_resume
from .jd import analyze_jd
from .pdf import extract_text

app = FastAPI(title="TalentGraph API")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])

_tasks: set[asyncio.Task] = set()   # keep refs so background tasks aren't garbage collected


def now():
    return datetime.now(timezone.utc)


def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except InvalidId:
        raise HTTPException(404, "Not found")


def clean(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if "batch_id" in doc:
        doc["batch_id"] = str(doc["batch_id"])
    return doc


@app.on_event("startup")
async def indexes():
    try:
        db = get_db()
        await db.candidates.create_index("batch_id")
        await db.batches.create_index("created_at")
    except Exception as e:  # don't crash the container; /api/health will show it
        print("Mongo index setup failed:", e)


@app.get("/api/health")
async def health():
    try:
        await get_db().command("ping")
        return {"status": "ok", "db": "up"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)[:120]}


async def run_batch(batch_id: ObjectId, jd_text: str, resumes: list[tuple[str, str]], threshold: int):
    db = get_db()
    try:
        jd = await analyze_jd(jd_text)
        await db.batches.update_one({"_id": batch_id}, {"$set": {"jd": jd, "status": "screening"}})
        sem = asyncio.Semaphore(config.LLM_CONCURRENCY)

        async def one(filename: str, text: str):
            async with sem:
                try:
                    doc = {**await screen_resume(text, jd, threshold), "status": "done"}
                except Exception as e:
                    doc = {"status": "error", "error": f"{type(e).__name__}: {str(e)[:200]}", "score": -1}
            doc.update(batch_id=batch_id, filename=filename, created_at=now())
            await db.candidates.insert_one(doc)
            await db.batches.update_one({"_id": batch_id}, {"$inc": {"completed": 1}})

        await asyncio.gather(*(one(f, t) for f, t in resumes))
        await db.batches.update_one({"_id": batch_id}, {"$set": {"status": "done", "finished_at": now()}})
    except Exception as e:
        await db.batches.update_one({"_id": batch_id},
                                    {"$set": {"status": "failed", "error": f"{type(e).__name__}: {str(e)[:200]}"}})


async def read_upload(f: UploadFile) -> tuple[str, str]:
    data = await f.read()
    if len(data) > config.MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds {config.MAX_FILE_MB}MB")
    return f.filename, await run_in_threadpool(extract_text, f.filename, data)


@app.post("/api/batches", status_code=202)
async def create_batch(
    resumes: list[UploadFile] = File(...),
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    threshold: int = Form(70),
):
    if not 0 <= threshold <= 100:
        raise HTTPException(422, "threshold must be 0-100")
    if not 1 <= len(resumes) <= config.MAX_RESUMES:
        raise HTTPException(422, f"Upload between 1 and {config.MAX_RESUMES} resumes")

    if jd_file and jd_file.filename:
        try:
            _, jd_text = await read_upload(jd_file)
        except ValueError as e:
            raise HTTPException(422, f"JD file: {e}")
    jd_text = jd_text.strip()
    if len(jd_text) < 50:
        raise HTTPException(422, "Provide a job description (text or PDF)")

    parsed, failed = [], []
    for f in resumes:
        try:
            parsed.append(await read_upload(f))
        except ValueError as e:
            failed.append((f.filename, str(e)))

    db = get_db()
    res = await db.batches.insert_one({
        "status": "parsing", "created_at": now(), "total": len(resumes), "completed": len(failed),
        "threshold": threshold, "jd_chars": len(jd_text), "jd_preview": jd_text[:200], "jd": None,
    })
    if failed:
        await db.candidates.insert_many([
            {"batch_id": res.inserted_id, "filename": n, "status": "error", "error": e,
             "score": -1, "created_at": now()} for n, e in failed])

    task = asyncio.create_task(run_batch(res.inserted_id, jd_text, parsed, threshold))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"batch_id": str(res.inserted_id)}


@app.get("/api/batches")
async def list_batches():
    docs = await get_db().batches.find({}, {"jd_preview": 0}).sort("created_at", -1).limit(20).to_list(20)
    out = []
    for d in docs:
        d = clean(d)
        d["title"] = (d.get("jd") or {}).get("title", "Analyzing JD...")
        d.pop("jd", None)
        out.append(d)
    return out


@app.get("/api/batches/{batch_id}")
async def get_batch(batch_id: str):
    db = get_db()
    batch = await db.batches.find_one({"_id": oid(batch_id)})
    if not batch:
        raise HTTPException(404, "Not found")
    cands = await db.candidates.find({"batch_id": batch["_id"]}).sort("score", -1).to_list(200)
    return {**clean(batch), "candidates": [clean(c) for c in cands]}


@app.delete("/api/batches/{batch_id}", status_code=204)
async def delete_batch(batch_id: str):
    db = get_db()
    await db.candidates.delete_many({"batch_id": oid(batch_id)})
    await db.batches.delete_one({"_id": oid(batch_id)})
