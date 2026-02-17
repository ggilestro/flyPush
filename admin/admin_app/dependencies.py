"""FastAPI dependencies: DB session and admin auth guard."""

from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from admin_app.auth import validate_session_token
from admin_app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=3,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(request: Request) -> str:
    """Dependency that enforces admin session. Returns username."""
    token = request.cookies.get("admin_session")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    username = validate_session_token(token)
    if not username:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return username
