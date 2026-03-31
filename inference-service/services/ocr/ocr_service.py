"""
Tesseract OCR サービス

スキャン PDF のフォールバック OCR として使用。
WSL2等の推論ノードで実行され、文字列と単語のバウンディングボックスを返す。
"""

import io
from typing import Tuple, List, Dict

import pytesseract
from PIL import Image

from common import settings
from common.logger import logger
from common.ocr import ocrmypdf_run


class TesseractOcrService:
    """Tesseract を使ったテキスト認識サービス。"""

    def __init__(self) -> None:
        self.lang: str = settings.get("TESSERACT_LANG", "eng")
        self.config: str = settings.get("TESSERACT_CONFIG", "--oem 1 --psm 3")
        logger.info(f"TesseractOcrService initialized with lang={self.lang}, config={self.config}")

    def ocr_page(self, img_bytes: bytes, bboxes: List[Dict] | None = None) -> Tuple[str, List[Dict]]:
        """
        ページ画像からテキストと単語座標を抽出する。
        (非同期環境からスレッドプールで呼ばれることを想定)

        Args:
            img_bytes: JPEG/PNG 等の画像バイト
            bboxes: 未使用（将来のテキスト領域限定 OCR のためのシグネチャ予約）
        Returns:
            (認識テキスト, 単語リスト)
        """
        try:
            # グレースケール変換: Tesseract は内部でグレースケール処理するため
            # RGB のまま渡すと不要なメモリ確保が発生する
            img = Image.open(io.BytesIO(img_bytes)).convert("L")

            # image_to_data の1回呼び出しでテキストと単語 bbox を同時取得
            # (旧実装: image_to_string + image_to_pdf_or_hocr の2回呼び出し)
            data = pytesseract.image_to_data(
                img,
                lang=self.lang,
                config=self.config,
                output_type=pytesseract.Output.DICT,
            )

            n = len(data["text"])
            words: list[dict] = []
            line_texts: dict[tuple, list[str]] = {}

            for i in range(n):
                word = data["text"][i].strip()
                conf = int(data["conf"][i])
                if not word or conf < 10:
                    continue

                x0, y0 = data["left"][i], data["top"][i]
                x1, y1 = x0 + data["width"][i], y0 + data["height"][i]
                words.append({"word": word, "bbox": [x0, y0, x1, y1], "conf": conf / 100.0})

                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                line_texts.setdefault(key, []).append(word)

            text = "\n".join(" ".join(ws) for _, ws in sorted(line_texts.items()))
            return text, words

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise

    def ocr_pdf_to_searchable(self, pdf_bytes: bytes) -> bytes:
        """
        スキャン PDF にテキストレイヤーを付与してサーチャブル PDF を返す。

        ocrmypdf を使用。ネイティブテキストが既にあるページはスキップ（skip_text=True）。
        GROBID に渡す前処理として使用することを想定。

        Args:
            pdf_bytes: 入力 PDF のバイト列
        Returns:
            テキストレイヤー付き PDF のバイト列
        Raises:
            concurrent.futures.TimeoutError: 全体処理タイムアウト（240秒）
            Exception: OCRmyPDF の実行に失敗した場合
        """
        import concurrent.futures

        logger.info(f"ocr_pdf_to_searchable: starting OCRmyPDF (lang={self.lang}, size={len(pdf_bytes)})")

        # ProcessPoolExecutor でサブプロセス化し、タイムアウト超過時に強制終了できるようにする
        # ocrmypdf_run はモジュールレベル関数（pickle 可能）
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ocrmypdf_run, pdf_bytes, self.lang)
            result = future.result(timeout=240)  # 240秒で全体タイムアウト

        logger.info(f"ocr_pdf_to_searchable: done (output size={len(result)})")
        return result
