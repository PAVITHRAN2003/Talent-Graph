import os

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "talentgraph")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "3"))

MAX_RESUMES = 25
MAX_FILE_MB = 10
MAX_RESUME_CHARS = 30_000     # a resume is never longer than this in practice
JD_CHUNK_CHARS = 12_000       # JDs longer than this go through map-reduce
