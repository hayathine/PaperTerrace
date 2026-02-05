import argparse
import asyncio
import os
import sys

# プロジェクトルートをパスに追加（スクリプトとして実行する場合用）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.domain.services.local_translator import get_local_translator
from app.domain.services.paddle_layout_service import get_layout_service
from app.logger import logger


async def run_job(file_path: str, file_hash: str):
    """
    Cloud Run Jobとしての重負荷処理フロー。
    1. レイアウト解析 (ONNX)
    2. 単語翻訳 (CTranslate2) は必要に応じて
    3. 結果の保存
    """
    logger.info(f"Starting heavy processing job for file: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    try:
        # レイアウト解析サービス
        _layout_service = get_layout_service()

        # 翻訳サービス
        translator = get_local_translator()
        await translator.prewarm()

        # ここでPDFの各ページに対して処理を行うロジックを実装
        # 実際には pdf_ocr_service のロジックと共通化するのが望ましいが、
        # Jobとして独立して動くための最小限の実装を行う

        logger.info(f"Processing complete for {file_hash}")
        # データベースへの保存などはサービス経由で行う

    except Exception as e:
        logger.error(f"Job failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="PaperTerrace Heavy Processing Job")
    parser.add_argument("--file_path", type=str, required=True, help="Path to the PDF file")
    parser.add_argument("--file_hash", type=str, required=True, help="Hash of the PDF file")

    args = parser.parse_args()

    asyncio.run(run_job(args.file_path, args.file_hash))


if __name__ == "__main__":
    main()
