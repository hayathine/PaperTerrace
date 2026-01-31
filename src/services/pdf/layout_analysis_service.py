import cv2
import layoutparser as lp
import numpy as np
from PIL import Image

from src.logger import logger


class LayoutAnalysisService:
    def __init__(self):
        # PubLayNet is good for Figure, Table, Text, Title, List
        # Note: Equations are not explicitly in PubLayNet, but sometimes grouped near Figures
        self.model = lp.AutoLayoutModel(
            "lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
            label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
        )

    def analyze_layout(self, image_pil: Image.Image):
        """
        Analyze layout using layoutparser.
        Returns a list of detected blocks with labels and coordinates.
        """
        try:
            # Convert PIL to openCV format (BGR)
            image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

            # Detect layout
            layout = self.model.detect(image_cv)

            blocks = []
            for block in layout:
                # LayoutParser uses [x1, y1, x2, y2]
                blocks.append(
                    {
                        "type": block.type,
                        "bbox": [
                            block.block.x_1,
                            block.block.y_1,
                            block.block.x_2,
                            block.block.y_2,
                        ],
                        "score": block.score,
                    }
                )

            return blocks
        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return []

    @staticmethod
    def filter_blocks(blocks, types=["Figure", "Table"]):
        """Filter blocks by type."""
        return [b for b in blocks if b["type"] in types]
