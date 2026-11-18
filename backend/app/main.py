from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import campaigns, editor, health, operations, references
from app.config import get_settings
from app.db.session import init_db
from app.db.sqlite_paths import SqliteDatabaseStartupError, ensure_sqlite_database_ready

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        try:
            path = ensure_sqlite_database_ready(settings.database_url)
            logger.info("SQLite ready at %s", path)
        except SqliteDatabaseStartupError as exc:
            logger.error("%s", exc)
            raise RuntimeError(str(exc)) from exc
    init_db()
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(references.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(editor.router, prefix="/api")