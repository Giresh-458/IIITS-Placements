from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from src.config.settings import settings
from src.storage.models.outreach import Base
import logging

class DatabaseManager:
    """
    Database connection management and repository interfaces.
    Uses PostgreSQL as source of truth via asyncpg.
    """
    def __init__(self, db_url: str = None):
        # We can substitute a test DB url (like sqlite) if needed
        self.db_url = db_url or settings.database_url
        if self.db_url.startswith("sqlite://"):
            self.db_url = self.db_url.replace("sqlite://", "sqlite+aiosqlite://")
        self.engine = None
        self.session_maker = None

    async def connect(self):
        logging.info(f"Connecting to DB: {self.db_url}")
        # Need to fix sqlite url if testing
        connect_args = {}
        if "sqlite" in self.db_url:
            connect_args["check_same_thread"] = False
            
        self.engine = create_async_engine(self.db_url, echo=False, connect_args=connect_args)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
            
    async def disconnect(self):
        if self.engine:
            await self.engine.dispose()

    async def check_health(self) -> bool:
        if not self.engine:
            return False
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logging.error(f"DB Health check failed: {e}")
            return False

    def get_session(self) -> AsyncSession:
        return self.session_maker()
