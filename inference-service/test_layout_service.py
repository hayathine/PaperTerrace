#!/usr/bin/env python3
"""
Test script for LayoutAnalysisService
"""

import logging

# Add services to path
import os
import sys
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from services.layout_detection.layout_service import LayoutAnalysisService
except ImportError as e:
    # Print more detailed error info for debugging
    logging.error(f"Failed to import LayoutAnalysisService: {e}")
    # Also check if paddleocr is missing
    try:
        import paddleocr
    except ImportError:
        logging.error(
            "PaddleOCR module is missing. It seems it is not installed in the current environment."
        )
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_test_image():
    """Find a test image in common locations"""
    candidates = [
        Path("test_page.png"),
        Path("../test_page.png"),
        Path("../backend/test_page.png"),
        Path("/home/gwsgs/work_space/paperterrace/backend/test_page.png"),
    ]
    for path in candidates:
        if path.exists():
            return str(path.absolute())
    return None


def test_service_flow():
    """Test the full service flow"""
    logger.info("=" * 60)
    logger.info("TEST: LayoutAnalysisService Flow")
    logger.info("=" * 60)

    image_path = find_test_image()
    if not image_path:
        logger.warning("⚠ No test image found. Skipping functional tests.")
        return

    logger.info(f"Using test image: {image_path}")

    try:
        # 1. Initialization
        # Note: The new service requires image_path at init
        service = LayoutAnalysisService(image_path=image_path)
        logger.info("✓ Service initialized")

        # 2. Analysis
        logger.info("Running analysis...")
        results = service.analysis()

        # 3. Validation
        logger.info("✓ Analysis completed")
        logger.info(f"  Detected items: {len(results)}")

        for i, item in enumerate(results):
            # Item is expected to be a LayoutItem (Pydantic model) or dict
            # The current implementation might return dicts inside the list
            if isinstance(item, dict):
                logger.info(
                    f"    [{i}] Class: {item.get('class_id')}, Score: {item.get('score'):.2f}, BBox: {item.get('bbox')}"
                )
            else:
                # If it's a Pydantic model
                logger.info(f"    [{i}] {item}")

    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_service_flow()
