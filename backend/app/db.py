import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from . import config

_client = None


def get_db():
    global _client
    if _client is None:
        if not config.MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not set")
        _client = AsyncIOMotorClient(config.MONGODB_URI, tlsCAFile=certifi.where(),
                                     serverSelectionTimeoutMS=8000)
    return _client[config.MONGODB_DB]
