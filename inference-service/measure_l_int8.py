import os
import sys
import time
import asyncio
import cv2
import fitz

# Add the inference-service directory to sys.path so we can import services
sys.path.append(os.getcwd())

from services.layout_detection.openvino_layout_service import OpenVINOLayoutAnalysisService

async def measure_speed_and_save_images(pdf_path, model_path, output_dir, num_pages=5):
    if not os.path.exists(pdf_path):
        print(f"Error: pdf not found at {pdf_path}")
        return 0

    os.makedirs(output_dir, exist_ok=True)
    
    # Check if model exists
    if not os.path.exists(model_path):
        print(f"Error: model not found at {model_path}")
        return 0

    print(f"--- Loading Model: {model_path} ---")
    service = OpenVINOLayoutAnalysisService(model_path=model_path)
    # Ensure threshold set to 0.5 for consistent benchmarking
    service.threshold = 0.5
    
    doc = fitz.open(pdf_path)
    actual_pages = min(len(doc), num_pages)
    
    print(f"Extracting {actual_pages} pages...")
    img_paths = []
    for i in range(actual_pages):
        page = doc[i]
        # Using 150 DPI for standard analysis
        pix = page.get_pixmap(dpi=150)
        img_path = f"tmp_page_{i}.png"
        pix.save(img_path)
        img_paths.append(img_path)
    
    # Warm-up (1 iteration)
    print("Warm-up...")
    await service.analyze_image(img_paths[0])
    
    # Measure
    print(f"Measuring speed on {actual_pages} pages...")
    start_time = time.time()
    # Using batch analysis as it represents realistic production speed
    all_results = await service.analyze_images_batch(img_paths)
    elapsed = time.time() - start_time
    
    avg_per_page = elapsed / actual_pages
    print(f"Total time (Inference + Post-process): {elapsed:.4f}s")
    print(f"Average time per page: {avg_per_page:.4f}s")
    
    # Save Images
    print(f"Saving detection images to {output_dir}...")
    for i, (orig_img_path, results) in enumerate(zip(img_paths, all_results)):
        img = cv2.imread(orig_img_path)
        for item in results:
            bbox = item.bbox
            x1, y1, x2, y2 = int(bbox.x_min), int(bbox.y_min), int(bbox.x_max), int(bbox.y_max)
            # Render BBox
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{item.class_name}:{item.score:.2f}", (x1, max(y1-5, 0)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        out_path = os.path.join(output_dir, f"page_{i+1:03d}.jpg")
        cv2.imwrite(out_path, img)
        # Cleanup temp image
        if os.path.exists(orig_img_path):
            os.remove(orig_img_path)
    
    doc.close()
    return avg_per_page

async def main():
    pdf_path = "../backend/sample.pdf"
    int8_model = "models/paddl2vino/PP-DocLayout-L_int8.xml"
    fp16_model = "models/paddl2vino/PP-DocLayout-L_fp16.xml"
    fp32_model = "models/paddl2vino/PP-DocLayout-L_infer.xml"
    
    results = {}
    
    print("\n" + "="*40)
    print("=== Benchmarking INT8 Model ===")
    print("="*40)
    results["INT8"] = await measure_speed_and_save_images(pdf_path, int8_model, "output_int8", num_pages=5)
    
    print("\n" + "="*40)
    print("=== Benchmarking FP16 Model ===")
    print("="*40)
    results["FP16"] = await measure_speed_and_save_images(pdf_path, fp16_model, "output_fp16", num_pages=5)

    print("\n" + "="*40)
    print("=== Benchmarking FP32 Model ===")
    print("="*40)
    results["FP32"] = await measure_speed_and_save_images(pdf_path, fp32_model, "output_fp32", num_pages=5)
    
    print("\n" + "="*80)
    print(" " * 30 + "FINAL SUMMARY")
    print("="*80)
    print(f"{'Model':<20} | {'Average Time/Page':<25}")
    print("-" * 80)
    for model, t in results.items():
        print(f"{model:<20} | {t:.4f} s")
    
    if results["INT8"] > 0 and results["FP32"] > 0:
        print("-" * 80)
        print(f"Speedup INT8 vs FP32: {results['FP32'] / results['INT8']:.2f}x")
        print(f"Speedup INT8 vs FP16: {results['FP16'] / results['INT8']:.2f}x")
        print(f"Speedup FP16 vs FP32: {results['FP32'] / results['FP16']:.2f}x")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
