"""
Tesseract OCR サービス

スキャン PDF のフォールバック OCR として使用。
WSL2等の推論ノードで実行され、文字列と単語のバウンディングボックスを返す。
"""

import io
import re
from typing import Tuple, List, Dict, Any

from PIL import Image
from lxml import etree
import pytesseract

from common import settings
from common.logger import logger


class TesseractOcrService:
    """Tesseract を使ったテキスト認識サービス。"""

    def __init__(self) -> None:
        self.lang: str = settings.get("TESSERACT_LANG", "eng+jpn")
        self.config: str = settings.get("TESSERACT_CONFIG", "--oem 1 --psm 3")
        logger.info(f"TesseractOcrService initialized with lang={self.lang}, config={self.config}")

    def _parse_hocr_words(self, hocr_bytes: bytes, img_width: int, img_height: int) -> List[Dict[str, Any]]:
        """
        Tesseract の hOCR 出力から単語レベルの bbox を抽出する。

        Args:
            hocr_bytes: pytesseract.image_to_pdf_or_hocr() の hOCR 出力
            img_width: 元画像の幅（px）
            img_height: 元画像の高さ（px）

        Returns:
            [{"word": str, "bbox": [x0, y0, x1, y1], "conf": float}, ...]
        """
        words: List[Dict[str, Any]] = []
        try:
            root = etree.fromstring(hocr_bytes)
            ns = root.nsmap.get(None, "")
            tag_prefix = f"{{{ns}}}" if ns else ""
            span_tag = f"{tag_prefix}span"

            for span in root.iter(span_tag):
                cls = span.get("class", "")
                if "ocrx_word" not in cls:
                    continue
                title = span.get("title", "")
                word_text = (span.text_content() if hasattr(span, "text_content") else "".join(span.itertext())).strip()
                if not word_text:
                    continue

                # "bbox x0 y0 x1 y1; x_wconf NN" をパース
                bbox_match = re.search(r"bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", title)
                conf_match = re.search(r"x_wconf\s+(\d+)", title)
                if not bbox_match:
                    continue

                x0, y0, x1, y1 = (int(bbox_match.group(i)) for i in range(1, 5))
                conf = int(conf_match.group(1)) / 100.0 if conf_match else 1.0

                # 信頼度が低い単語（10%未満）はノイズとして除外
                if conf < 0.1:
                    continue

                words.append({"word": word_text, "bbox": [x0, y0, x1, y1], "conf": conf})
        except Exception as e:
            logger.warning(f"Failed to parse hOCR words: {e}")

        return words

    def ocr_page(self, img_bytes: bytes, bboxes: List[Dict] | None = None) -> Tuple[str, List[Dict]]:
        """
        ページ画像からテキストと単語座標を抽出する。
        (非同期環境からスレッドプールで呼ばれることを想定)

        Args:
            img_bytes: JPEG/PNG 等の画像バイト
            bboxes: テキスト領域のリスト（Tesseractでは現在は無視しページ全体を解析する設計としておく）
        Returns:
            (認識テキスト, 単語リスト)
        """
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            
            # TODO: `bboxes` が指定された場合は領域ごとにOCRする実装の追加も可能だが
            # 現在のフォールバックはページ全体を想定している
            
            text = pytesseract.image_to_string(img, lang=self.lang, config=self.config)
            hocr_bytes = pytesseract.image_to_pdf_or_hocr(
                img, lang=self.lang, config=self.config, extension="hocr"
            )
            
            words = self._parse_hocr_words(hocr_bytes, img.width, img.height)
            return text.strip(), words
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
