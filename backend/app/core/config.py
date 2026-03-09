"""
環境設定モジュール。
APP_ENV 環境変数 (prod | dev) に応じて、Neon・BigQuery の接続先を切り替える。
"""

import os

from common.logger import ServiceLogger

log = ServiceLogger("Config")


def get_app_env() -> str:
    """
    現在の環境を返す。
    'production' -> 'prod'
    'development' -> 'dev'
    未設定の場合は 'dev' を返す。
    """
    env = os.getenv("APP_ENV", "dev").lower()
    if env == "production":
        return "prod"
    if env == "development":
        return "dev"
    return env


def is_production() -> bool:
    return get_app_env() == "prod"


def get_database_url() -> str:
    """環境に応じた Neon PostgreSQL 接続 URL を返す。"""
    if is_production():
        url = os.getenv("DATABASE_URL")
    else:
        url = os.getenv("DATABASE_URL_DEV") or os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError(
            f"DATABASE_URL{'_DEV' if not is_production() else ''} が設定されていません"
        )

    env = get_app_env()
    log.info("config", f"Database URL resolved (env={env})")
    return url


def get_neon_auth_jwks_url() -> str | None:
    """環境に応じた Neon Auth JWKS URL を返す。"""
    if is_production():
        return os.getenv("NEON_AUTH_JWKS_URL")
    return os.getenv("NEON_AUTH_JWKS_URL_DEV") or os.getenv("NEON_AUTH_JWKS_URL")


def get_neon_auth_url() -> str | None:
    """環境に応じた Neon Auth URL を返す。"""
    if is_production():
        return os.getenv("NEON_AUTH_URL")
    return os.getenv("NEON_AUTH_URL_DEV") or os.getenv("NEON_AUTH_URL")


def get_bq_log_dataset() -> str:
    """環境に応じた BigQuery ログデータセット名を返す。"""
    if is_production():
        return os.getenv("BQ_LOG_DATASET", "paperterrace_logs")
    return os.getenv("BQ_LOG_DATASET_DEV", "paperterrace_logs_dev")
