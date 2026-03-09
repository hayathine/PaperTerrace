import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Import DB config from storage provider or env
def get_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        dbname = os.getenv("DB_NAME")

        if all([user, password, host, dbname]):
            # Cloud SQL uses postgresql
            return f"postgresql://{user}:{password}@{host}/{dbname}"

        db_path = os.getenv("DB_PATH", "ocr_reader.db")
        url = f"sqlite:///{db_path}"

    # SQLAlchemy requires postgresql:// instead of postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


engine = create_engine(get_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_orm_storage():
    """
    FastAPI Depends 用: リクエストスコープの ORMStorageAdapter を返す。

    使い方:
        from fastapi import Depends
        from app.database import get_orm_storage
        from app.providers.orm_storage import ORMStorageAdapter

        @router.get("/example")
        async def example(storage: ORMStorageAdapter = Depends(get_orm_storage)):
            ...
    """
    from app.providers.orm_storage import ORMStorageAdapter

    db = SessionLocal()
    try:
        yield ORMStorageAdapter(db)
    finally:
        db.close()
