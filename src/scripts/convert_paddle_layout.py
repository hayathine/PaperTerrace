"""
Paddle Layout Model to ONNX Converter

This script converts PaddleOCR's layout detection model to ONNX format
for optimized CPU inference using ONNX Runtime.

Usage:
    python -m src.scripts.convert_paddle_layout

Requirements:
    - paddlepaddle
    - paddle2onnx
    - ppstructure (from paddleocr)
"""

import os

# Set paddle to use CPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""


def convert_model():
    output_dir = "models"
    onnx_path = os.path.join(output_dir, "layout_m.onnx")

    if os.path.exists(onnx_path):
        print(f"ONNX model already exists at {onnx_path}. Skipping conversion.")
        return

    print("Converting PaddleOCR Layout Model to ONNX format...")
    print("This requires paddlepaddle and paddle2onnx to be installed.")

    try:
        from paddle2onnx import export

        # Download and load the layout model
        from paddleocr import PPStructure

        # Initialize PPStructure to download model (engine not used directly)
        _engine = PPStructure(  # noqa: F841
            layout=True,
            table=False,
            ocr=False,
            recovery=False,
            lang="en",
            show_log=False,
        )

        # Find the downloaded model path
        # PaddleOCR typically stores models in ~/.paddleocr/
        home = os.path.expanduser("~")
        paddle_cache = os.path.join(home, ".paddleocr")

        # Look for layout model
        layout_model_dir = None
        for root, dirs, files in os.walk(paddle_cache):
            if "picodet_lcnet_x1_0_fgd_layout_infer" in root:
                layout_model_dir = root
                break

        if not layout_model_dir:
            print("Error: Could not find downloaded layout model.")
            print("Please ensure PPStructure was initialized successfully.")
            return

        print(f"Found layout model at: {layout_model_dir}")

        # Convert to ONNX
        model_file = os.path.join(layout_model_dir, "model.pdmodel")
        params_file = os.path.join(layout_model_dir, "model.pdiparams")

        if not os.path.exists(model_file) or not os.path.exists(params_file):
            print(f"Error: Model files not found in {layout_model_dir}")
            return

        os.makedirs(output_dir, exist_ok=True)

        # Export to ONNX
        export(
            model_file=model_file,
            params_file=params_file,
            save_file=onnx_path,
            opset_version=14,
            enable_onnx_checker=True,
        )

        print(f"Conversion complete. ONNX model saved to: {onnx_path}")

        # Verify the model
        try:
            import onnxruntime as ort

            session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            print("ONNX model verification successful.")
            print(f"Input: {session.get_inputs()[0].name} - {session.get_inputs()[0].shape}")
            print(f"Outputs: {[o.name for o in session.get_outputs()]}")
        except Exception as e:
            print(f"Warning: ONNX verification failed: {e}")

    except ImportError as e:
        print(f"Error: Missing required package - {e}")
        print("Please install: pip install paddlepaddle paddle2onnx paddleocr")


if __name__ == "__main__":
    convert_model()
