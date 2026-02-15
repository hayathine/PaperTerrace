import logging
import os
import sys

import cv2

# Adjust path to import backend modules
sys.path.append("/home/gwsgs/work_space/paperterrace/backend")
sys.path.append("/home/gwsgs/work_space/paperterrace/inference-service")

# Mock logger configuration
logging.basicConfig(level=logging.INFO)

from services.layout_detection.layout_service import LayoutAnalysisService


def test_layout_service():
    # Initialize service
    # Make sure to point to the correct model path if needed, or rely on default
    model_path = "/home/gwsgs/work_space/paperterrace/inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx"
    # Fallback to checking where the model actually is
    if not os.path.exists(model_path):
        # unexpected, but let's try to find it
        # Try finding via list_dir logic if known, but for now assuming standard path or relative
        pass

    service = LayoutAnalysisService(model_path=model_path)

    # Use one of the found images
    image_path = "/home/gwsgs/work_space/paperterrace/backend/src/static/paper_images/e4c88891d6a634ea3c145710f4424fd2f9e611c37e4a05144c87a8602e7577a4/page_1.png"

    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return

    print(f"Testing with image: {image_path}")

    # Get image input size
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    print(f"Original Image Size: {w}x{h}")

    try:
        results = service.analyze_image(image_path)

        print("\n--- Detection Results ---")
        for item in results:
            bbox = item.bbox
            print(
                f"Label: {item.class_name}, Score: {item.score:.4f}, BBox: [{bbox.x_min}, {bbox.y_min}, {bbox.x_max}, {bbox.y_max}]"
            )

            # Sanity check
            if bbox.x_max > w or bbox.y_max > h:
                print("  WARNING: BBox exceeds image boundary!")
            if bbox.x_max < 640 and bbox.y_max < 640 and w > 1000:
                print("  WARNING: BBox seems too small (possibly scaled down?)")

    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_layout_service()
