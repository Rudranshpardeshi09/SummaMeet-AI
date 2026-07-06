import os
from dotenv import load_dotenv
load_dotenv("../../.env")
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_note_taker")

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
