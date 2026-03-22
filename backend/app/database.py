
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse

from common.config import settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


def get_url():
    # 環境に応じた DB URL を取得（staging: DATABASE_URL_STAGING, local: DATABASE_URL_LOCAL）
    try:
        from app.core.config import get_database_url
        url = get_database_url()
    except Exception:
        # get_database_url が失敗した場合（ローカル開発でDBが未設定など）は個別変数にフォールバック
        url = settings.get("DATABASE_URL")
        if not url:
            user = settings.get("DB_USER")
            password = settings.get("DB_PASSWORD")
            host = settings.get("DB_HOST")
            dbname = settings.get("DB_NAME")

            if all([user, password, host, dbname]):
                url = f"postgresql://{user}:{password}@{host}/{dbname}"
            else:
                db_path = settings.get("DB_PATH", "ocr_reader.db")
                url = f"sqlite:///{db_path}"

    if not url:
        db_path = settings.get("DB_PATH", "ocr_reader.db")
        url = f"sqlite:///{db_path}"

    # SQLAlchemy requires postgresql:// instead of postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def _to_neon_pooler_url(url: str) -> str | None:
    """Neon の direct endpoint URL を pgbouncer pooler URL に変換する。

    例: ep-cool-name-123456.us-east-2.aws.neon.tech
     →  ep-cool-name-123456-pooler.us-east-2.aws.neon.tech
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if ".neon.tech" in host and "-pooler" not in host:
            # ホスト名の最初のセグメント（エンドポイントID）に -pooler を付加
            first_dot = host.index(".")
            new_host = host[:first_dot] + "-pooler" + host[first_dot:]
            new_netloc = parsed.netloc.replace(host, new_host)
            return urlunparse(parsed._replace(netloc=new_netloc))
    except Exception:
        pass
    return None


_url = get_url()
_is_postgres = _url.startswith("postgresql")

_connect_args = {}
if _is_postgres:
    # TCP keepalive でサーバー側の突然切断を防ぐ (Cloud Run / Neon 向け)
    _connect_args = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

# Neon pgbouncer pooler endpoint の解決
# 優先順位:
#   1. DATABASE_POOL_URL 環境変数（明示的な pooler URL）
#   2. DATABASE_URL が Neon URL の場合、自動的に pooler hostname に変換
#   3. DATABASE_URL が既に Neon pooler URL の場合、そのまま使用
#   4. フォールバック: 通常の QueuePool
_pool_url = settings.get("DATABASE_POOL_URL", "")
if not _pool_url and _is_postgres:
    _pool_url = _to_neon_pooler_url(_url) or ""
    # DATABASE_URL が既に pooler エンドポイントの場合もNullPoolを使用
    if not _pool_url:
        try:
            from urllib.parse import urlparse as _urlparse
            _h = _urlparse(_url).hostname or ""
            if ".neon.tech" in _h and "-pooler" in _h:
                _pool_url = _url
        except Exception:
            pass

_use_pgbouncer = bool(_pool_url)

if _use_pgbouncer:
    # NullPool: pgbouncer 側で接続プールを管理するため SQLAlchemy のプールは不要。
    # トランザクションモードの pgbouncer では prepared statement が使えないが、
    # psycopg2 + SQLAlchemy はデフォルトでサーバーサイド prepared statement を使わないため問題なし。
    engine = create_engine(
        _pool_url,
        poolclass=NullPool,
        connect_args=_connect_args,
    )
else:
    # 通常の QueuePool（non-Neon PostgreSQL または SQLite）
    engine = create_engine(
        _url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5 if _is_postgres else 5,
        max_overflow=10 if _is_postgres else 10,
        connect_args=_connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass  # SSL切断等でロールバック自体が失敗しても無視
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass  # SSL切断等でロールバック自体が失敗しても無視
        raise
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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
