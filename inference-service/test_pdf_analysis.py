#!/usr/bin/env python3
"""
Test script for PDF Layout Analysis using test_light.pdf
"""

import logging
import sys
from pathlib import Path
import tempfile
import os
import time

# Add services to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from services.layout_detection.layout_service import LayoutAnalysisService, LayoutItem, BBox
except ImportError as e:
    logging.error(f"Failed to import LayoutAnalysisService: {e}")
    sys.exit(1)

# PDF処理用のライブラリ
try:
    import pdfplumber
    from PIL import Image
except ImportError as e:
    logging.error(f"Required libraries not installed: {e}")
    logging.error("Please install with: pip install pdfplumber Pillow")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_pdf_file():
    """Find test_heavy.pdf file"""
    candidates = [
        Path("frontend/public/test_heavy.pdf"),
        Path("../frontend/public/test_heavy.pdf"),
        Path("/home/gwsgs/work_space/paperterrace/frontend/public/test_heavy.pdf"),
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


def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """
    Convert PDF pages to images using pdfplumber
    
    Parameters
    ----------
    pdf_path : str
        Path to PDF file
    output_dir : str
        Directory to save images
    dpi : int
        Resolution for image conversion
        
    Returns
    -------
    list[str]
        List of image file paths
    """
    logger.info(f"Converting PDF to images: {pdf_path}")
    
    image_paths = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                # Convert page to image
                # pdfplumber returns PIL Image
                pil_image = page.to_image(resolution=dpi).original
                
                # Save image
                image_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
                pil_image.save(image_path, "PNG")
                image_paths.append(image_path)
                
                logger.info(f"  Page {page_num + 1} -> {image_path}")
                
            except Exception as e:
                logger.error(f"  Failed to convert page {page_num + 1}: {e}")
                continue
    
    logger.info(f"Converted {len(image_paths)} pages")
    return image_paths


def analyze_pdf_layout(pdf_path: str, model_path: str) -> dict:
    """
    Analyze PDF layout using ONNX model
    
    Parameters
    ----------
    pdf_path : str
        Path to PDF file
    model_path : str
        Path to ONNX model
        
    Returns
    -------
    dict
        Analysis results for all pages
    """
    logger.info("=" * 60)
    logger.info("PDF Layout Analysis")
    logger.info("=" * 60)
    
    # Create temporary directory for images
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Using temporary directory: {temp_dir}")
        
        # Convert PDF to images
        image_paths = pdf_to_images(pdf_path, temp_dir)
        
        results = {}
        
        # Analyze each page
        for i, image_path in enumerate(image_paths):
            page_num = i + 1
            logger.info(f"\nAnalyzing page {page_num}...")
            
            # Start timing for this page
            page_start_time = time.time()
            
            try:
                # Initialize service for this image
                init_start_time = time.time()
                service = LayoutAnalysisService(
                    image_path=image_path,
                    model_path=model_path
                )
                init_time = time.time() - init_start_time
                
                # Run analysis
                analysis_start_time = time.time()
                page_results = service.analysis()
                analysis_time = time.time() - analysis_start_time
                
                # Calculate total page time
                total_page_time = time.time() - page_start_time
                
                # Log timing information
                logger.info(f"  ⏱️  Page {page_num} timing:")
                logger.info(f"    - Model initialization: {init_time:.3f}s")
                logger.info(f"    - Analysis execution: {analysis_time:.3f}s")
                logger.info(f"    - Total page time: {total_page_time:.3f}s")
                
                results[f"page_{page_num}"] = {
                    "image_path": image_path,
                    "detections": page_results,
                    "timing": {
                        "init_time": init_time,
                        "analysis_time": analysis_time,
                        "total_time": total_page_time
                    },
                    "summary": {
                        "total_items": len(page_results),
                        "by_class": {}
                    }
                }
                
                # Count by class
                class_counts = {}
                for item in page_results:
                    class_id = item.get("class_id", -1)
                    class_counts[class_id] = class_counts.get(class_id, 0) + 1
                
                results[f"page_{page_num}"]["summary"]["by_class"] = class_counts
                
                # Log results
                logger.info(f"  📊 Page {page_num} results:")
                logger.info(f"    Total detections: {len(page_results)}")
                
                for class_id, count in class_counts.items():
                    if class_id < len(LayoutAnalysisService.LABELS):
                        class_name = LayoutAnalysisService.LABELS[class_id]
                    else:
                        class_name = f"Unknown_{class_id}"
                    logger.info(f"    {class_name}: {count}")
                
                # Show detailed results
                for j, item in enumerate(page_results):
                    class_id = item.get("class_id", -1)
                    score = item.get("score", 0)
                    bbox = item.get("bbox", [])
                    
                    if class_id < len(LayoutAnalysisService.LABELS):
                        class_name = LayoutAnalysisService.LABELS[class_id]
                    else:
                        class_name = f"Unknown_{class_id}"
                    
                    logger.info(f"      [{j}] {class_name} (score: {score:.3f})")
                    logger.info(f"          BBox: {bbox}")
                
            except Exception as e:
                total_page_time = time.time() - page_start_time
                logger.error(f"  ❌ Failed to analyze page {page_num} (time: {total_page_time:.3f}s): {e}")
                results[f"page_{page_num}"] = {
                    "error": str(e),
                    "image_path": image_path,
                    "timing": {
                        "total_time": total_page_time,
                        "failed": True
                    }
                }
    
    return results


def print_summary(results: dict):
    """Print analysis summary"""
    logger.info("\n" + "=" * 60)
    logger.info("ANALYSIS SUMMARY")
    logger.info("=" * 60)
    
    total_pages = len(results)
    successful_pages = sum(1 for r in results.values() if "detections" in r)
    failed_pages = total_pages - successful_pages
    
    logger.info(f"Total pages: {total_pages}")
    logger.info(f"Successfully analyzed: {successful_pages}")
    logger.info(f"Failed: {failed_pages}")
    
    # Timing summary
    total_time = 0
    total_init_time = 0
    total_analysis_time = 0
    timing_pages = 0
    
    for page_key, page_data in results.items():
        if "timing" in page_data and not page_data["timing"].get("failed", False):
            timing_pages += 1
            total_time += page_data["timing"]["total_time"]
            total_init_time += page_data["timing"].get("init_time", 0)
            total_analysis_time += page_data["timing"].get("analysis_time", 0)
    
    if timing_pages > 0:
        avg_total_time = total_time / timing_pages
        avg_init_time = total_init_time / timing_pages
        avg_analysis_time = total_analysis_time / timing_pages
        
        logger.info(f"\n⏱️  Timing Summary:")
        logger.info(f"  Total processing time: {total_time:.3f}s")
        logger.info(f"  Average per page:")
        logger.info(f"    - Total time: {avg_total_time:.3f}s")
        logger.info(f"    - Model init: {avg_init_time:.3f}s")
        logger.info(f"    - Analysis: {avg_analysis_time:.3f}s")
        logger.info(f"  Processing rate: {timing_pages/total_time:.2f} pages/second")
    
    if successful_pages > 0:
        # Aggregate statistics
        total_detections = 0
        class_totals = {}
        
        for page_key, page_data in results.items():
            if "detections" in page_data:
                total_detections += page_data["summary"]["total_items"]
                
                for class_id, count in page_data["summary"]["by_class"].items():
                    class_totals[class_id] = class_totals.get(class_id, 0) + count
        
        logger.info(f"\n📊 Detection Summary:")
        logger.info(f"  Total detections across all pages: {total_detections}")
        logger.info(f"  Average detections per page: {total_detections/successful_pages:.1f}")
        logger.info("  Detections by class:")
        
        for class_id, count in sorted(class_totals.items()):
            if class_id < len(LayoutAnalysisService.LABELS):
                class_name = LayoutAnalysisService.LABELS[class_id]
            else:
                class_name = f"Unknown_{class_id}"
            percentage = (count / total_detections) * 100
            logger.info(f"    {class_name}: {count} ({percentage:.1f}%)")


def main():
    """Run PDF analysis test"""
    logger.info("\n" + "=" * 60)
    logger.info("PDF Layout Analysis Test (test_heavy.pdf)")
    logger.info("=" * 60 + "\n")
    
    # Find files
    pdf_path = find_pdf_file()
    model_path = find_onnx_model()
    
    if not pdf_path:
        logger.error("❌ test_heavy.pdf not found!")
        logger.info("Expected locations:")
        logger.info("  - frontend/public/test_heavy.pdf")
        logger.info("  - ../frontend/public/test_heavy.pdf")
        sys.exit(1)
    
    if not model_path:
        logger.error("❌ ONNX model not found!")
        logger.info("Expected locations:")
        logger.info("  - ./models/paddle2onnx/PP-DocLayout-S_infer.onnx")
        logger.info("  - ../models/paddle2onnx/PP-DocLayout-S_infer.onnx")
        sys.exit(1)
    
    logger.info(f"✅ PDF file: {pdf_path}")
    logger.info(f"✅ ONNX model: {model_path}")
    
    try:
        # Record total start time
        total_start_time = time.time()
        
        # Run analysis
        results = analyze_pdf_layout(pdf_path, model_path)
        
        # Calculate total time
        total_elapsed_time = time.time() - total_start_time
        
        # Print summary
        print_summary(results)
        
        logger.info(f"\n🕒 Total execution time: {total_elapsed_time:.3f}s")
        logger.info("\n" + "=" * 60)
        logger.info("✅ PDF Analysis completed successfully!")
        logger.info("=" * 60 + "\n")
        
        return results
        
    except Exception as e:
        logger.error(f"\n❌ PDF Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()