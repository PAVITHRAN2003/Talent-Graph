from functools import lru_cache
from langchain_groq import ChatGroq
from . import config


@lru_cache
def get_llm() -> ChatGroq:
    # max_retries gives automatic exponential backoff on Groq 429s
    return ChatGroq(model=config.GROQ_MODEL, temperature=0, max_retries=5, timeout=90)


async def structured(schema, prompt: str):
    """Single choke point for every LLM call -> validated Pydantic object.
    Tries strict JSON-schema mode first, then tool-calling, retrying on failure."""
    last = None
    for method in ("json_schema", "function_calling", "json_schema"):
        try:
            return await get_llm().with_structured_output(schema, method=method).ainvoke(prompt)
        except Exception as e:
            last = e
    raise last