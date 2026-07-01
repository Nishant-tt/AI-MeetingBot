import asyncio
import asyncpg
from app.config import settings


async def test():
    db_url = settings.database_url.replace("+asyncpg", "")

    conn = await asyncpg.connect(db_url)

    print("Connected successfully")

    db = await conn.fetchval("SELECT current_database();")
    print("Database:", db)

    await conn.close()


asyncio.run(test())