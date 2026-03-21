import os
import sys
import time
import asyncio

# Add the inference-service directory to sys.path so we can import services
sys.path.append(os.getcwd())

from services.layout_detection.layout_service import LayoutAnalysisService
from services.layout_detection.openvino_layout_service import OpenVINOLayoutAnalysisService

async def benchmark():
    image_path = "../test_page1.jpg"
    if not os.path.exists(image_path):
        print(f"Error: image not found at {image_path}")
        return

    print(f"Benchmarking on {image_path} (Batch size 4)")
    image_paths = [image_path] * 4
    
    # 1. Initialize ONNX Service
    print("\n--- Initializing ONNX Service ---")
    onnx_service = LayoutAnalysisService(
        model_path="models/paddle2onnx/PP-DocLayout-L_infer.onnx"
    )
    
    # 2. Warm-up ONNX
    print("Warm-up ONNX...")
    onnx_service.analyze_images_batch(image_paths)
    
    # 3. Benchmark ONNX
    print("Measuring ONNX (Batch 4)...")
    onnx_times = []
    for i in range(5):
        start = time.time()
        onnx_service.analyze_images_batch(image_paths)
        onnx_times.append(time.time() - start)
        print(f"  Iteration {i+1}: {onnx_times[-1]:.4f}s")
    
    avg_onnx = sum(onnx_times) / len(onnx_times)
    print(f"Average ONNX Batch 4: {avg_onnx:.4f}s")

    # 4. Initialize OpenVINO Service
    print("\n--- Initializing OpenVINO Service ---")
    ov_service = OpenVINOLayoutAnalysisService(
        model_path="models/paddl2vino/PP-DocLayout-L_infer.xml"
    )
    
    # 5. Warm-up OpenVINO
    print("Warm-up OpenVINO...")
    await ov_service.analyze_images_batch(image_paths)
    
    # 6. Benchmark OpenVINO
    print("Measuring OpenVINO (Batch 4)...")
    ov_times = []
    for i in range(5):
        start = time.time()
        await ov_service.analyze_images_batch(image_paths)
        ov_times.append(time.time() - start)
        print(f"  Iteration {i+1}: {ov_times[-1]:.4f}s")
    
    avg_ov = sum(ov_times) / len(ov_times)
    print(f"Average OpenVINO Batch 4: {avg_ov:.4f}s")
    
    print("\n--- Summary (Batch 4) ---")
    print(f"ONNX Average:     {avg_onnx:.4f}s")
    print(f"OpenVINO Average: {avg_ov:.4f}s")
    print(f"Speedup:          {avg_onnx / avg_ov:.2f}x")

if __name__ == "__main__":
    asyncio.run(benchmark())
