import logging
import os
import sys

import structlog
from structlog.typing import EventDict, WrappedLogger


def flatten_extra(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    'extra' 引数が渡された場合（標準logging互換）、
    その内容をフラットに展開して構造化データに含めるプロセッサ。
    """
    extra = event_dict.pop("extra", None)
    if extra and isinstance(extra, dict):
        event_dict.update(extra)
    return event_dict


# 共通のプロセッサ定義
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.dev.set_exc_info,
    structlog.processors.format_exc_info,
    flatten_extra,  # extra={...} のサポート
]


def configure_logging():
    """
    structlog と 標準 logging の統合設定。
    """
    # ログ設定の取得
    log_format = os.getenv("LOG_FORMAT", "console").lower()
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # structlog の設定
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 標準logging（stdlib）の設定
    # これにより、他ライブラリからのログもstructlog形式に変換される
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # ハンドラの作成
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # ルートロガーの設定
    root_logger = logging.getLogger()
    # 既存のハンドラをクリアして二重出力を防ぐ
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # 主要なライブラリのロガー設定
    # これらのロガーの伝搬(propagate)を有効にし、独自ハンドラを削除することで、
    # ルートロガーのハンドラ（structlog形式）で出力されるようにする
    target_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "alembic",
        "fastapi",
        "starlette",
        "sqlalchemy",
    ]
    for logger_name in target_loggers:
        log = logging.getLogger(logger_name)
        for h in log.handlers[:]:
            log.removeHandler(h)
        log.propagate = True

    # アプリケーションロガーのレベル設定
    logging.getLogger("app_logger").setLevel(log_level)


# 初期化実行
configure_logging()

# アプリケーション全体で利用するロガー
logger = structlog.get_logger("app_logger")
