"""
Structured logging configuration for PaperTerrace.

このモジュールはアプリケーション全体の統一されたロギングを提供します。
"""

import logging
import sys
from datetime import datetime, timedelta, timezone

import structlog
from structlog.typing import EventDict, WrappedLogger


def flatten_extra(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    'extra' 引数が渡された場合（標準logging互換）、
    その内容をフラットに展開してJSONのルートに含めるプロセッサ。
    """
    extra = event_dict.pop("extra", None)
    if extra and isinstance(extra, dict):
        event_dict.update(extra)
    return event_dict


def add_service_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    サービスコンテキスト（service, operation）を自動追加するプロセッサ。
    """
    # eventからサービス情報を抽出（例: "[PDF.analyze]" -> service="PDF", operation="analyze"）
    event = event_dict.get("event", "")
    if event.startswith("[") and "]" in event:
        bracket_end = event.index("]")
        tag = event[1:bracket_end]
        if "." in tag:
            parts = tag.split(".", 1)
            event_dict["service"] = parts[0]
            event_dict["operation"] = parts[1]
        else:
            event_dict["service"] = tag
    return event_dict


def jst_timestamper(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    タイムスタンプをJSTで付与するプロセッサ。
    """
    jst = timezone(timedelta(hours=9))
    event_dict["timestamp"] = datetime.now(jst).isoformat()
    return event_dict


# 共通のプロセッサ定義
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    jst_timestamper,
    structlog.processors.StackInfoRenderer(),
    structlog.dev.set_exc_info,
    structlog.processors.format_exc_info,
    flatten_extra,
    add_service_context,
]


def configure_logging(log_level: str = "INFO"):
    """ロギングを設定する"""
    import os

    # 環境変数からログレベルを取得（デフォルトはINFO）
    env_log_level = os.getenv("LOG_LEVEL", log_level).upper()

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)  # stderrからstdoutに変更
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, env_log_level))

    logging.getLogger("app_logger").setLevel(getattr(logging, env_log_level))

    # uvicornのログ設定
    for logger_name in ["uvicorn", "uvicorn.error"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        uv_logger.propagate = True

    # 静的ファイルアクセスログの設定（環境変数で制御）
    access_log_level = os.getenv("ACCESS_LOG_LEVEL", "WARNING").upper()
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, access_log_level))

    # 設定されたログレベルを出力
    print(
        f"Logging configured: level={env_log_level}, access_log={access_log_level}",
        file=sys.stdout,
        flush=True,
    )


# 初期化実行
configure_logging()

# アプリケーション全体で利用するロガー
logger = structlog.get_logger("app_logger")


class ServiceLogger:
    """
    サービス固有のロガー。
    タグを自動的に付与して一貫したログ出力を提供。

    Usage:
        log = ServiceLogger("PDF")
        log.info("analyze", "Processing file", filename="test.pdf")
        # Output: {"event": "[PDF.analyze] Processing file", "filename": "test.pdf", ...}
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._logger = structlog.get_logger("app_logger")

    def _format_event(self, operation: str, message: str) -> str:
        return f"[{self.service_name}.{operation}] {message}"

    def debug(self, operation: str, message: str, **kwargs):
        self._logger.debug(self._format_event(operation, message), **kwargs)

    def info(self, operation: str, message: str, **kwargs):
        self._logger.info(self._format_event(operation, message), **kwargs)

    def warning(self, operation: str, message: str, **kwargs):
        self._logger.warning(self._format_event(operation, message), **kwargs)

    def error(self, operation: str, message: str, **kwargs):
        self._logger.error(self._format_event(operation, message), **kwargs)

    def exception(self, operation: str, message: str, **kwargs):
        self._logger.exception(self._format_event(operation, message), **kwargs)


def get_service_logger(service_name: str) -> ServiceLogger:
    """サービス固有のロガーを取得する"""
    return ServiceLogger(service_name)
