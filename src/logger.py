import logging
import sys

import structlog
from structlog.typing import EventDict, WrappedLogger


def flatten_extra(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    'extra' 引数が渡された場合（標準logging互換）、
    その内容をフラットに展開してJSONのルートに含めるプロセッサ。
    例: logger.info("msg", extra={"user_id": 1}) -> {"event": "msg", "user_id": 1, ...}
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
    # structlog の設定
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 標準logging（stdlib）の設定
    # これにより、他ライブラリからのログもstructlog経由でJSON出力されるようにする
    formatter = structlog.stdlib.ProcessorFormatter(
        # stdlibのログレコードをstructlog形式に変換する前の処理
        foreign_pre_chain=shared_processors,
        # 最終的な出力フォーマッター
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    # Clear existing handlers to avoid duplication or conflicts
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # 既存の app_logger があれば設定を適用
    logging.getLogger("app_logger").setLevel(logging.INFO)

    # uvicornのログもルートに伝播させるように設定（uvicornは独自の設定を持つため）
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        uv_logger.propagate = True


# 初期化実行
configure_logging()

# アプリケーション全体で利用するロガー
logger = structlog.get_logger("app_logger")
