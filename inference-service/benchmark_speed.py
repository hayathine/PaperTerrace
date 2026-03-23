import fitz
import os
import sys
import time

sys.path.append(os.getcwd())
from services.layout_detection.layout_service import LayoutAnalysisService

def benchmark_speed(pdf_path, num_pages=10):
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    actual_pages = min(len(doc), num_pages)
    
    # Extract images first to only measure inference time
    img_paths = []
    print(f"Extracting {actual_pages} pages for benchmarking...")
    for i in range(actual_pages):
        page = doc[i]
        pix = page.get_pixmap(dpi=150)
        img_path = f"tmp_bench_page_{i}.png"
        pix.save(img_path)
        img_paths.append(img_path)
        
    doc.close()
    
    models = {
        "S": "models/paddle2onnx/PP-DocLayout-S_infer.onnx",
        "M": "models/paddle2onnx/PP-DocLayout-M_infer.onnx",
        "L": "models/paddle2onnx/PP-DocLayout-L_infer.onnx"
    }
    
    thresholds = [0.2, 0.5]
    results = {}
    
    for thresh in thresholds:
        print(f"\n--- Benchmark at Threshold: {thresh} ---")
        for size, path in models.items():
            if not os.path.exists(path):
                print(f"Model {size} not found at {path}")
                continue
                
            service = LayoutAnalysisService(model_path=path)
            service.threshold = thresh
            
            # Warmup
            service.analyze_image(img_paths[0])
            
            # Benchmark
            start_time = time.time()
            total_elements = 0
            
            for img_path in img_paths:
                layout_results = service.analyze_image(img_path)
                total_elements += len(layout_results)
                
            elapsed = time.time() - start_time
            avg_time = elapsed / len(img_paths)
            
            print(f"Model {size}: {elapsed:.4f}s total | {avg_time:.4f}s per page | Elements found: {total_elements}")
            results[(thresh, size)] = (avg_time, total_elements)
            
    # Cleanup
    for img_path in img_paths:
        if os.path.exists(img_path):
            os.remove(img_path)
            
    # Print Markdown Table to console for easy copy/paste
    print("\n### Benchmark Results (Average Processing Time per Page)")
    print("| Model | Threshold 0.2 | Threshold 0.5 | Elements (0.2) | Elements (0.5) |")
    print("|---|---|---|---|---|")
    for size in ["S", "M", "L"]:
        t02_time, t02_elem = results.get((0.2, size), (0, 0))
        t05_time, t05_elem = results.get((0.5, size), (0, 0))
        print(f"| {size} | {t02_time:.4f} s | {t05_time:.4f} s | {t02_elem} | {t05_elem} |")

if __name__ == "__main__":
    pdf_file = "../backend/sample.pdf"
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    benchmark_speed(pdf_file, num_pages=20)
