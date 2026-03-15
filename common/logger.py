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
    # eventからサービス情報を抽出（例: "[PDF.analyze] message" -> service="PDF", operation="analyze"）
    # すでにフィールドにある場合はスキップ
    if "service" in event_dict or "operation" in event_dict:
        # もしブラケット形式のメッセージなら、メッセージ側をクリーンアップするオプションも検討できるが、
        # ここでは単にフィールド付与をスキップするにとどめる
        return event_dict

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


def add_severity_level(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Cloud Logging 用に 'severity' フィールドを追加する。
    structlog の 'level' を GCP が期待する 'severity' (大文字) にマッピングする。
    """
    if "level" in event_dict:
        event_dict["severity"] = event_dict["level"].upper()
    return event_dict


# 共通のプロセッサ定義
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    add_severity_level,  # severityを追加
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
    env_log_level = (os.getenv("LOG_LEVEL") or log_level).upper()

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
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
    for logger_name in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "httpx",
        "httpcore",
    ]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        uv_logger.propagate = True

        # 外部ライブラリのログを抑制
        if logger_name in ["uvicorn.access", "httpx", "httpcore"]:
            level = logging.WARNING
            if logger_name == "uvicorn.access":
                level = getattr(
                    logging, os.getenv("ACCESS_LOG_LEVEL", "WARNING").upper()
                )
            uv_logger.setLevel(level)

    # 静的ファイルアクセスログの設定（環境変数で制御）
    access_log_level = os.getenv("ACCESS_LOG_LEVEL", "WARNING").upper()

    # サードパーティライブラリのデバッグログを抑制（アプリのLOG_LEVELに関係なくWARNING以上のみ）
    noisy_loggers = [
        # PDF処理
        "pdfminer",
        "pdfminer.pdfdocument",
        "pdfminer.pdfparser",
        "pdfminer.pdfpage",
        "pdfminer.pdfinterp",
        "pdfminer.converter",
        "pdfminer.cmapdb",
        "pdfminer.layout",
        # HTTP通信
        "urllib3",
        "urllib3.connectionpool",
        "urllib3.util.retry",
        "requests",
        # Google Cloud
        "google.auth",
        "google.auth.transport",
        "google.cloud",
        "google.cloud.storage",
        "google.api_core",
        "googleapiclient",
        # その他
        "PIL",
        "charset_normalizer",
        "asyncio",
        "multipart",
        "aiohttp",
        "grpc",
    ]
    for noisy_logger_name in noisy_loggers:
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

    # 設定されたログレベルを出力
    print(
        f"Logging configured: level={env_log_level}, access_log={access_log_level}",
        file=sys.stdout,
        flush=True,
    )


def get_logger(name: str):
    """標準的なロガー取得のための関数（後方互換性のため）"""
    return structlog.get_logger(name)


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

    def _log(self, level: str, operation: str, message: str, **kwargs):
        """内部共通ロギングメソッド"""
        method = getattr(self._logger, level)

        # kwargs内のservice/operationと衝突しないように退避
        log_data = kwargs.copy()
        if "service" in log_data:
            log_data["target_service"] = log_data.pop("service")
        if "operation" in log_data:
            log_data["target_operation"] = log_data.pop("operation")

        method(message, service=self.service_name, operation=operation, **log_data)

    def debug(self, operation: str, message: str, **kwargs):
        self._log("debug", operation, message, **kwargs)

    def info(self, operation: str, message: str, **kwargs):
        self._log("info", operation, message, **kwargs)

    def warning(self, operation: str, message: str, **kwargs):
        self._log("warning", operation, message, **kwargs)

    def error(self, operation: str, message: str, **kwargs):
        self._log("error", operation, message, **kwargs)

    def exception(self, operation: str, message: str, **kwargs):
        self._log("exception", operation, message, **kwargs)


def get_service_logger(service_name: str) -> ServiceLogger:
    """サービス固有のロガーを取得する"""
    return ServiceLogger(service_name)
