import asyncio
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import config
from .llm import structured
from .schemas import JDRequirements

EXTRACT = """Extract structured hiring requirements from this job description{part}.
Use short canonical skill names (e.g. "Python", "AWS", "REST APIs").

JOB DESCRIPTION:
{text}"""

MERGE = """Below are partial requirement extractions from consecutive chunks of ONE long job description.
Merge them into a single JDRequirements: dedupe skills, keep the true job title, take the max of
min_years_experience, and keep only the 8 most important responsibilities.

PARTIALS:
{partials}"""


async def analyze_jd(text: str) -> dict:
    """Short JD -> one call. Long JD -> map-reduce over chunks so nothing blows the context window."""
    if len(text) <= config.JD_CHUNK_CHARS:
        res = await structured(JDRequirements, EXTRACT.format(part="", text=text))
        return res.model_dump()

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=config.JD_CHUNK_CHARS, chunk_overlap=500
    ).split_text(text)
    sem = asyncio.Semaphore(config.LLM_CONCURRENCY)

    async def one(i, c):
        async with sem:
            return await structured(
                JDRequirements, EXTRACT.format(part=f" (part {i + 1}/{len(chunks)})", text=c)
            )

    partials = await asyncio.gather(*(one(i, c) for i, c in enumerate(chunks)))
    merged = await structured(
        JDRequirements,
        MERGE.format(partials=json.dumps([p.model_dump() for p in partials])),
    )
    return merged.model_dump()
