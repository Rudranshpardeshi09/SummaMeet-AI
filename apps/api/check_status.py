import asyncio
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from sqlalchemy import select

async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(Meeting))
        for m in result.scalars().all():
            print(f"Meeting {m.id} status: {m.status}")

if __name__ == "__main__":
    asyncio.run(main())
