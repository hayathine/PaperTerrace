"""
環境設定モジュール。

common.config の dynaconf settings 経由で設定を取得する。
APP_ENV 環境変数 (prod | staging | local) に応じて、Neon・BigQuery の接続先を切り替える。
  - prod    : 本番環境 (Cloud Run)
  - staging : 開発/staging 環境 (k8s)
  - local   : ローカル開発環境 (デフォルト)
"""



from common.config import get_redis_url, settings
from common.logger import ServiceLogger

log = ServiceLogger("Config")


def get_app_env() -> str:
    """
    現在の環境を正規化して返す。

    受け付ける APP_ENV 値:
      'prod' | 'production' -> 'prod'    (本番環境)
      'staging'             -> 'staging' (開発/staging 環境)
      'local' | 未設定     -> 'local'   (ローカル開発環境)
    """
    env = str(settings.get("APP_ENV", "local")).lower()
    if env in ("production", "prod"):
        return "prod"
    if env == "staging":
        return "staging"
    return "local"


def is_production() -> bool:
    return get_app_env() == "prod"


def is_staging() -> bool:
    return get_app_env() == "staging"


def is_local() -> bool:
    return get_app_env() == "local"


def get_database_url() -> str:
    """環境に応じた Neon PostgreSQL 接続 URL を返す。

    優先順位:
      prod    : DATABASE_URL
      staging : DATABASE_URL_STAGING → DATABASE_URL
      local   : DATABASE_URL_LOCAL   → DATABASE_URL
    """
    env = get_app_env()
    if env == "prod":
        url = settings.get("DATABASE_URL")
        suffix = ""
    elif env == "staging":
        url = settings.get("DATABASE_URL_STAGING") or settings.get("DATABASE_URL")
        suffix = "_STAGING"
    else:
        url = settings.get("DATABASE_URL_LOCAL") or settings.get("DATABASE_URL")
        suffix = "_LOCAL"

    if not url:
        raise RuntimeError(
            f"DATABASE_URL{suffix} が設定されていません"
        )

    log.info("config", f"Database URL resolved (env={env})")
    return url


def get_neon_auth_jwks_url() -> str | None:
    """環境に応じた Neon Auth JWKS URL を返す。"""
    if is_production():
        return settings.get("NEON_AUTH_JWKS_URL")
    return (
        settings.get("NEON_AUTH_JWKS_URL_LOCAL")
        or settings.get("NEON_AUTH_JWKS_URL")
    )


def get_neon_auth_url() -> str | None:
    """環境に応じた Neon Auth URL を返す。"""
    if is_production():
        return settings.get("NEON_AUTH_URL")
    return (
        settings.get("NEON_AUTH_URL_LOCAL")
        or settings.get("NEON_AUTH_URL")
    )


def get_bq_log_dataset() -> str:
    """環境に応じた BigQuery ログデータセット名を返す。"""
    if is_production():
        return settings.get("BQ_LOG_DATASET", "paperterrace_logs")
    if is_staging():
        return settings.get("BQ_LOG_DATASET_STAGING", "paperterrace_logs_staging")
    return settings.get("BQ_LOG_DATASET_LOCAL", "paperterrace_logs_local")


def get_gcs_bucket_name() -> str | None:
    """環境に応じた GCS バケット名を返す。

    環境別の優先順位:
      prod    : GCS_BUCKET_NAME
      staging : GCS_BUCKET_NAME_STAGING → GCS_BUCKET_NAME
      local   : GCS_BUCKET_NAME_LOCAL   → GCS_BUCKET_NAME
    """
    if is_production():
        return settings.get("GCS_BUCKET_NAME")
    if is_staging():
        return settings.get("GCS_BUCKET_NAME_STAGING") or settings.get("GCS_BUCKET_NAME")
    return settings.get("GCS_BUCKET_NAME_LOCAL") or settings.get("GCS_BUCKET_NAME")


def get_worker_api_url() -> str | None:
    """Worker API の URL を返す。未設定の場合は None（Redis 直接モード）。

    環境別の優先順位:
      prod    : WORKER_API_URL
      staging : WORKER_API_URL_STAGING → WORKER_API_URL
      local   : WORKER_API_URL_LOCAL   → None（ローカルは Redis 直接）
    """
    if is_production():
        return settings.get("WORKER_API_URL") or None
    if is_staging():
        return (
            settings.get("WORKER_API_URL_STAGING")
            or settings.get("WORKER_API_URL")
            or None
        )
    return settings.get("WORKER_API_URL_LOCAL") or None


# get_redis_url は common.config から re-export
__all__ = ["get_redis_url"]
