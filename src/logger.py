import logging

from pythonjsonlogger import jsonlogger

# ロガーのセットアップ
logger = logging.getLogger("app_logger")
log_handler = logging.StreamHandler()  # stdoutに出力

# JSON形式のフォーマッターを設定
# ログに含めたい標準的な項目（時間、レベル、メッセージ）を指定
formatter = jsonlogger.JsonFormatter(
    "%(levelname)s %(message)s %(asctime)s", json_ensure_ascii=False
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)


# # --- 実際の使い方 ---
# @app.post("/analyze")
# async def analyze(text: str = Form(...)):
#     # 任意の値を 'extra' 引数で渡すと、JSONのキーとして追加されます
#     logger.info("Analyze started", extra={"user_id": 123, "text_length": len(text)})
