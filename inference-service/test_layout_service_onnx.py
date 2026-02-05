#!/usr/bin/env python3
"""
Test script for LayoutAnalysisService (ONNX版)
"""

import logging
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from services.layout_detection.layout_service import LayoutAnalysisService, LayoutItem, BBox
except ImportError as e:
    logging.error(f"Failed to import LayoutAnalysisService: {e}")
    sys.exit(1)

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
        Path("/home/gwsgs/work_space/paperterrace/test_page.png"),
    ]
    for path in candidates:
        if path.exists():
            return str(path.absolute())
    return None


def find_onnx_model():
    """Find ONNX model file"""
    candidates = [
        Path("./models/paddle2onnx/PP-DocLayout-S_infer.onnx"),
        Path("../models/paddle2onnx/PP-DocLayout-S_infer.onnx"),
        Path("./inference-service/models/paddle2onnx/PP-DocLayout-S_infer.onnx"),
    ]
    for path in candidates:
        if path.exists():
            return str(path.absolute())
    return None


def test_bbox_model():
    """Test BBox Pydantic model"""
    logger.info("=" * 60)
    logger.info("TEST 1: BBox Model")
    logger.info("=" * 60)
    
    try:
        # Test BBox creation
        bbox = BBox(x_min=10.0, y_min=20.0, x_max=100.0, y_max=200.0)
        logger.info(f"✓ BBox created: {bbox}")
        
        # Test from_list method
        bbox_from_list = BBox.from_list([10.0, 20.0, 100.0, 200.0])
        logger.info(f"✓ BBox from list: {bbox_from_list}")
        
        assert bbox == bbox_from_list, "BBox objects should be equal"
        logger.info("✓ BBox equality test passed")
        
    except Exception as e:
        logger.error(f"✗ BBox test failed: {e}")
        raise


def test_layout_item_model():
    """Test LayoutItem Pydantic model"""
    logger.info("=" * 60)
    logger.info("TEST 2: LayoutItem Model")
    logger.info("=" * 60)
    
    try:
        bbox = BBox(x_min=10.0, y_min=20.0, x_max=100.0, y_max=200.0)
        item = LayoutItem(bbox=bbox, score=0.95)
        logger.info(f"✓ LayoutItem created: {item}")
        
        # Test without score
        item_no_score = LayoutItem(bbox=bbox)
        logger.info(f"✓ LayoutItem without score: {item_no_score}")
        
    except Exception as e:
        logger.error(f"✗ LayoutItem test failed: {e}")
        raise


def test_service_initialization():
    """Test service initialization"""
    logger.info("=" * 60)
    logger.info("TEST 3: Service Initialization")
    logger.info("=" * 60)
    
    image_path = find_test_image()
    model_path = find_onnx_model()
    
    if not image_path:
        logger.warning("⚠ No test image found, using dummy path")
        image_path = "dummy.png"
    
    if not model_path:
        logger.warning("⚠ No ONNX model found, using default path")
        model_path = "./models/paddle2onnx/PP-DocLayout-S_infer.onnx"
    
    logger.info(f"Image path: {image_path}")
    logger.info(f"Model path: {model_path}")
    
    try:
        service = LayoutAnalysisService(
            image_path=image_path,
            model_path=model_path
        )
        logger.info("✓ Service initialized successfully")
        logger.info(f"  Input name: {service.input_name}")
        logger.info(f"  Image path: {service.image_path}")
        return service
        
    except FileNotFoundError as e:
        logger.warning(f"⚠ Model file not found: {e}")
        return None
    except Exception as e:
        logger.error(f"✗ Service initialization failed: {e}")
        raise


def test_preprocess():
    """Test preprocessing function"""
    logger.info("=" * 60)
    logger.info("TEST 4: Preprocessing")
    logger.info("=" * 60)
    
    image_path = find_test_image()
    if not image_path:
        logger.warning("⚠ No test image found, skipping preprocessing test")
        return
    
    try:
        # Note: _preprocess is a static method but returns 3 values now
        from services.layout_detection.layout_service import LayoutAnalysisService
        
        img, ori_shape, scale_factor = LayoutAnalysisService._preprocess(image_path)
        logger.info(f"✓ Preprocessing completed")
        logger.info(f"  Input shape: {img.shape}")
        logger.info(f"  Original shape: {ori_shape}")
        logger.info(f"  Scale factor shape: {scale_factor.shape}")
        
        # Validate shapes
        assert len(img.shape) == 4, f"Expected 4D tensor, got {img.shape}"
        assert img.shape[0] == 1, f"Expected batch size 1, got {img.shape[0]}"
        assert img.shape[1] == 3, f"Expected 3 channels, got {img.shape[1]}"
        assert scale_factor.shape == (1, 2), f"Expected scale_factor shape (1, 2), got {scale_factor.shape}"
        
        logger.info("✓ Shape validation passed")
        
    except Exception as e:
        logger.error(f"✗ Preprocessing test failed: {e}")
        import traceback
        traceback.print_exc()


def test_full_analysis():
    """Test full analysis pipeline"""
    logger.info("=" * 60)
    logger.info("TEST 5: Full Analysis Pipeline")
    logger.info("=" * 60)
    
    image_path = find_test_image()
    model_path = find_onnx_model()
    
    if not image_path:
        logger.warning("⚠ No test image found, skipping analysis test")
        return
    
    if not model_path:
        logger.warning("⚠ No ONNX model found, skipping analysis test")
        return
    
    try:
        service = LayoutAnalysisService(
            image_path=image_path,
            model_path=model_path
        )
        
        logger.info("Running full analysis...")
        results = service.analysis()
        
        logger.info(f"✓ Analysis completed successfully")
        logger.info(f"  Detected items: {len(results)}")
        
        # Validate results
        assert isinstance(results, list), "Results should be a list"
        
        for i, item in enumerate(results):
            if isinstance(item, dict):
                logger.info(f"  [{i}] Class: {item.get('class_id')}, Score: {item.get('score', 0):.3f}")
                logger.info(f"       BBox: {item.get('bbox')}")
            elif isinstance(item, LayoutItem):
                logger.info(f"  [{i}] Score: {item.score:.3f if item.score else 'N/A'}")
                logger.info(f"       BBox: {item.bbox}")
            else:
                logger.info(f"  [{i}] {item}")
        
        logger.info("✓ Results validation passed")
        return results
        
    except Exception as e:
        logger.error(f"✗ Full analysis test failed: {e}")
        import traceback
        traceback.print_exc()


def test_labels():
    """Test label mapping"""
    logger.info("=" * 60)
    logger.info("TEST 6: Label Mapping")
    logger.info("=" * 60)
    
    try:
        from services.layout_detection.layout_service import LayoutAnalysisService
        
        labels = LayoutAnalysisService.LABELS
        logger.info(f"✓ Labels loaded: {len(labels)} classes")
        
        for i, label in enumerate(labels):
            logger.info(f"  [{i}] {label}")
        
        # Validate important classes
        assert "Table" in labels, "Table class should be present"
        assert "Equation" in labels, "Equation class should be present"
        assert "Figure" in labels, "Figure class should be present"
        
        logger.info("✓ Label validation passed")
        
    except Exception as e:
        logger.error(f"✗ Label test failed: {e}")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("LayoutAnalysisService Test Suite (ONNX版)")
    logger.info("=" * 60 + "\n")
    
    try:
        # Test 1: BBox model
        test_bbox_model()
        
        # Test 2: LayoutItem model
        test_layout_item_model()
        
        # Test 3: Service initialization
        service = test_service_initialization()
        
        # Test 4: Preprocessing
        test_preprocess()
        
        # Test 5: Full analysis (if model available)
        if service:
            test_full_analysis()
        
        # Test 6: Labels
        test_labels()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests completed!")
        logger.info("=" * 60 + "\n")
        
    except Exception as e:
        logger.error(f"\n✗ Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()