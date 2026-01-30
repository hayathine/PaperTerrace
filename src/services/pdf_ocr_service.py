import base64
from typing import AsyncGenerator

import fitz  # PyMuPDF

from src.crud import get_ocr_from_db, save_ocr_to_db
from src.logger import logger
from src.prompts import (
    PDF_DETECT_LANGUAGE_PROMPT,
    PDF_EXTRACT_TEXT_OCR_PROMPT,
    VISION_DETECT_ITEMS_PROMPT,
)
from src.providers import get_ai_provider
from src.providers.image_storage import get_page_images, save_page_image
from src.schemas.figure import FigureDetectionResponse
from src.utils import _get_file_hash


class PDFOCRService:
    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model

    async def detect_language_from_pdf(self, file_bytes: bytes) -> str:
        """PDFの言語を検出する（メタデータ -> AI判定の順）"""
        language = "en"  # default

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")

            # 1. メタデータ (Catalog Lang) の確認
            catalog = doc.pdf_catalog()
            lang_entry = doc.xref_get_key(catalog, "Lang")
            if lang_entry[0] in ("name", "string") and lang_entry[1]:
                lang_code = lang_entry[1]
                logger.info(f"PDF Metadata Language detected: {lang_code}")
                # Clean up (e.g., 'en-US' -> 'en')
                language = lang_code.split("-")[0].lower()
                doc.close()
                return language

            # 2. メタデータにない場合、1ページ目をAIで判定
            if len(doc) > 0:
                text = doc[0].get_text()[:1000]
                if text.strip():
                    prompt = PDF_DETECT_LANGUAGE_PROMPT.format(text=text[:5000])
                    detected = await self.ai_provider.generate(prompt, model=self.model)
                    detected = detected.strip().lower()
                    if len(detected) == 2:
                        language = detected
                        logger.info(f"PDF Content Language detected by AI: {language}")

            doc.close()
        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        return language

    async def extract_text_streaming(
        self, file_bytes: bytes, filename: str = "unknown.pdf", user_plan: str = "free"
    ) -> AsyncGenerator:
        """ページ単位でOCR処理をストリーミングするジェネレータ。

        Yields:
            tuple: (page_num, total_pages, page_text, is_last, file_hash, page_image, layout_data)
        """
        file_hash = _get_file_hash(file_bytes)
        cached_ocr = get_ocr_from_db(file_hash)

        if cached_ocr:
            cached_images = get_page_images(file_hash)
            if cached_images:
                logger.info("Returning cached OCR text and images.")
                total_pages = len(cached_images)
                for i, img_url in enumerate(cached_images):
                    yield (
                        i + 1,
                        total_pages,
                        cached_ocr if i == 0 else "",
                        i == total_pages - 1,
                        file_hash,
                        img_url,
                        None,
                    )
                return
            else:
                logger.info("Cached OCR text found but images missing. Regenerating images.")

        logger.info(f"--- AI OCR Streaming: {filename} ---")

        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            logger.info(f"[OCR Streaming] Total pages: {total_pages}")

            all_text_parts = []

            for page_num in range(total_pages):
                page = pdf_doc[page_num]

                # ページ画像の生成 (2.0倍ズーム = 144 DPI 相当)
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                image_url = save_page_image(file_hash, page_num + 1, page_image_b64)

                # レイアウト情報の抽出
                words = page.get_text("words")
                layout_data = []
                page_text_extracted = ""

                img_width = pix.width
                img_height = pix.height

                if words:
                    word_list = []
                    for w in words:
                        word_list.append(
                            {
                                "word": w[4],
                                "bbox": [w[0] * zoom, w[1] * zoom, w[2] * zoom, w[3] * zoom],
                            }
                        )
                        page_text_extracted += w[4] + " "

                    layout_data = {
                        "width": img_width,
                        "height": img_height,
                        "words": word_list,
                    }

                    page_text = page_text_extracted.strip()
                    logger.info(f"[Layout] Extracted {len(words)} words from page {page_num + 1}")

                else:
                    # テキストがない場合はまずVision APIを試行
                    logger.info(
                        f"[OCR] No text found on page {page_num + 1}, trying Cloud Vision API"
                    )
                    layout_data = None
                    page_text = ""

                    try:
                        from src.providers.vision_ocr import VisionOCRService

                        vision_service = VisionOCRService()

                        if vision_service.is_available():
                            page_text, v_layout = await vision_service.detect_text_with_layout(
                                img_bytes
                            )

                            if v_layout and v_layout["words"]:
                                logger.info(
                                    f"[Vision OCR] Success: {len(v_layout['words'])} words detected"
                                )
                                v_layout["width"] = img_width
                                v_layout["height"] = img_height
                                layout_data = v_layout
                            else:
                                logger.warning(
                                    f"[Vision OCR] No text detected or failed. Text length: {len(page_text)}"
                                )

                    except Exception as e:
                        logger.error(f"[Vision OCR] Failed: {e}")

                    # Vision APIで失敗時はGeminiへフォールバック
                    if not page_text:
                        logger.info(f"[OCR] Falling back to Gemini for page {page_num + 1}")
                        single_page_pdf = fitz.open()
                        single_page_pdf.insert_pdf(pdf_doc, from_page=page_num, to_page=page_num)
                        single_page_pdf.close()

                        try:
                            page_text = await self.ai_provider.generate_with_image(
                                PDF_EXTRACT_TEXT_OCR_PROMPT,
                                img_bytes,
                                "image/png",
                                model=self.model,
                            )
                        except Exception as e:
                            logger.error(f"Gemini OCR failed for page {page_num + 1}: {e}")
                            page_text = ""

                        layout_data = None

                all_text_parts.append(page_text)
                is_last = page_num == total_pages - 1

                yield (
                    page_num + 1,
                    total_pages,
                    page_text,
                    is_last,
                    file_hash,
                    image_url,
                    layout_data,
                )

                # --- Figure Extraction (AI-Based) ---
                try:
                    # Detect figures/tables/equations using AI (Gemini) with structured output
                    detection_result: FigureDetectionResponse = (
                        await self.ai_provider.generate_with_image(
                            VISION_DETECT_ITEMS_PROMPT,
                            img_bytes,
                            "image/png",
                            response_model=FigureDetectionResponse,
                            model=self.model,
                        )
                    )

                    found_figures = detection_result.figures if detection_result else []

                    if found_figures:
                        logger.info(
                            f"[AI-Figure] Detected {len(found_figures)} items on page {page_num + 1}"
                        )

                        if layout_data is None:
                            layout_data = {
                                "width": img_width,
                                "height": img_height,
                                "words": [],
                            }
                        if isinstance(layout_data, list):  # Safety check
                            layout_data = {
                                "width": img_width,
                                "height": img_height,
                                "words": [],
                            }
                        if "figures" not in layout_data:
                            layout_data["figures"] = []

                        page_w = pix.width
                        page_h = pix.height

                        for i, fig in enumerate(found_figures):
                            try:
                                # box_2d is [ymin, xmin, ymax, xmax] normalized 0-1
                                ymin, xmin, ymax, xmax = fig.box_2d

                                # Convert to pixels (PyMuPDF Rect: x0, y0, x1, y1)
                                r_xmin = int(xmin * page_w)
                                r_ymin = int(ymin * page_h)
                                r_xmax = int(xmax * page_w)
                                r_ymax = int(ymax * page_h)

                                # Clip to page bounds
                                r_xmin = max(0, r_xmin)
                                r_ymin = max(0, r_ymin)
                                r_xmax = min(page_w, r_xmax)
                                r_ymax = min(page_h, r_ymax)

                                # Skip invalid or tiny boxes
                                if (r_xmax - r_xmin) < 10 or (r_ymax - r_ymin) < 10:
                                    continue

                                # Crop from the original page pixmap
                                # Note: fitz.IRect(x0, y0, x1, y1)
                                crop_rect = fitz.IRect(r_xmin, r_ymin, r_xmax, r_ymax)
                                crop_pix = fitz.Pixmap(pix, crop_rect)
                                crop_bytes = crop_pix.tobytes("png")

                                if (
                                    len(crop_bytes) < 500
                                ):  # Skip very small images (e.g. empty space)
                                    continue

                                crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")

                                # Generate filename/URL
                                # E.g. figure_page_index_label
                                figure_img_name_arg = f"figure_{page_num + 1}_{i}_{fig.label}"
                                figure_url = save_page_image(
                                    file_hash, figure_img_name_arg, crop_b64
                                )

                                # Add to layout data
                                layout_data["figures"].append(
                                    {
                                        "image_url": figure_url,
                                        "bbox": [
                                            r_xmin,
                                            r_ymin,
                                            r_xmax,
                                            r_ymax,
                                        ],  # Pixel coordinates
                                        "explanation": "",
                                        "page_num": page_num + 1,
                                        "label": fig.label,
                                    }
                                )

                            except Exception as crop_e:
                                logger.warning(
                                    f"[AI-Figure] Crop/Save failed for item {i}: {crop_e}"
                                )
                    else:
                        logger.debug(f"[AI-Figure] No figures detected on page {page_num + 1}")

                except Exception as e:
                    logger.warning(f"[AI-Figure] Extraction failed: {e}")

                yield (
                    page_num + 1,
                    total_pages,
                    page_text,
                    is_last,
                    file_hash,
                    image_url,
                    layout_data,
                )

            pdf_doc.close()

            # 全ページ処理完了後にDBに保存
            full_text = "\n\n---\n\n".join(all_text_parts)
            save_ocr_to_db(
                file_hash=file_hash,
                filename=filename,
                ocr_text=full_text,
                model_name=self.model,
            )
            logger.info(f"[OCR Streaming] Completed and saved: {filename}")

        except Exception as e:
            logger.error(f"OCR streaming failed: {e}")
            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash, None, None)
