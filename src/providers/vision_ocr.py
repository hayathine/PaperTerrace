"""
Google Cloud Vision API OCR Provider
Handles coordinate-based text extraction for image-based PDFs.
"""

import os
from typing import Any, Dict, Optional, Tuple

from google.cloud import vision

from src.logger import logger


class VisionOCRService:
    def __init__(self):
        self.client = None
        # Initialize client lazily or check env
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GCP_PROJECT"):
            try:
                self.client = vision.ImageAnnotatorClient()
            except Exception as e:
                logger.warning(f"Failed to initialize Vision API client: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    async def detect_text_with_layout(
        self, image_bytes: bytes
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Detect text using Vision API and return full text and layout data (words + bboxes).

        Args:
            image_bytes: PNG/JPEG image data

        Returns:
            (full_text, layout_data_dict)
            layout_data_dict format matches what src/logic.py expects:
            {
                "width": int,
                "height": int,
                "words": [
                    { "word": str, "bbox": [x0, y0, x1, y1] }
                ]
            }
        """
        if not self.client:
            return "", None

        try:
            image = vision.Image(content=image_bytes)
            # Use DOCUMENT_TEXT_DETECTION for better density handling in documents
            response = self.client.document_text_detection(image=image)

            if response.error.message:
                logger.error(f"Vision API Error: {response.error.message}")
                return f"Error: {response.error.message}", None

            # 1. Build full text
            full_text = response.full_text_annotation.text

            # 2. Build layout data
            # Vision API returns bounds in pixels relative to the image size.
            # We need to traverse pages -> blocks -> paragraphs -> words to construct lines/words.

            word_list = []

            # Since we send one image (page), there's usually just response.full_text_annotation.pages[0]
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([symbol.text for symbol in word.symbols])

                            # Get bounding box
                            # vertices typically 4 points: TL, TR, BR, BL
                            vertices = word.bounding_box.vertices

                            # Calculate x0, y0, x1, y1
                            x_coords = [v.x for v in vertices]
                            y_coords = [v.y for v in vertices]

                            x0 = min(x_coords)
                            y0 = min(y_coords)
                            x1 = max(x_coords)
                            y1 = max(y_coords)

                            word_list.append(
                                {
                                    "word": word_text,
                                    "bbox": [float(x0), float(y0), float(x1), float(y1)],
                                }
                            )

            layout_data = {
                "width": 0,  # These will be set by the caller usually, but Vision API also provides page size if needed
                "height": 0,
                "words": word_list,
            }

            # If the response includes page dimensions, we can use them as fallback or check
            if response.full_text_annotation.pages:
                layout_data["width"] = response.full_text_annotation.pages[0].width
                layout_data["height"] = response.full_text_annotation.pages[0].height

            return full_text, layout_data

        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            return "", None
