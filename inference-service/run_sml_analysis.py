import fitz
import os
import sys
import cv2
import time

sys.path.append(os.getcwd())
from services.layout_detection.layout_service import LayoutAnalysisService

def process_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    base_name = os.path.basename(pdf_path).split('.')[0]
    out_dir = f"../{base_name}_layout_images"
    os.makedirs(out_dir, exist_ok=True)
    
    models = {
        "S": "models/paddle2onnx/PP-DocLayout-S_infer.onnx",
        "M": "models/paddle2onnx/PP-DocLayout-M_infer.onnx",
        "L": "models/paddle2onnx/PP-DocLayout-L_infer.onnx"
    }
    
    # Check if models exist
    services = {}
    for size, path in models.items():
        if not os.path.exists(path):
            print(f"Model {size} not found at {path}")
            continue
        service = LayoutAnalysisService(model_path=path)
        service.threshold = 0.2
        services[size] = service
        
    if not services:
        print("No models available.")
        return

    for size, service in services.items():
        print(f"\n--- Processing for model {size} ---")
        
        for i in range(len(doc)):
            page = doc[i]
            # Use a slightly higher DPI for better inference and visualization
            pix = page.get_pixmap(dpi=150)
            img_path = f"tmp_page_{i}.png"
            pix.save(img_path)
            
            # Predict
            start = time.time()
            results = service.analyze_image(img_path)
            elapsed = time.time() - start
            print(f"  Page {i+1}/{len(doc)}, Time: {elapsed:.4f}s, Elements: {len(results)}")
            
            # Draw
            img = cv2.imread(img_path)
            for item in results:
                bbox = item.bbox
                x1, y1, x2, y2 = int(bbox.x_min), int(bbox.y_min), int(bbox.x_max), int(bbox.y_max)
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, f"{item.class_name}:{item.score:.2f}", (x1, max(y1-5, 0)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            out_img_path = os.path.join(out_dir, f"{base_name}_{size}_page_{i+1:03d}.jpg")
            cv2.imwrite(out_img_path, img)
            
            os.remove(img_path)
        
    doc.close()

if __name__ == "__main__":
    pdf_file = "../backend/sample.pdf"
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    process_pdf(pdf_file)
