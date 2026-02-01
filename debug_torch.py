import torch
import torchvision

print(f"Torch version: {torch.__version__}")
print(f"Torchvision version: {torchvision.__version__}")
try:
    print("NMS is available")
except Exception as e:
    print(f"NMS is NOT available: {e}")

try:
    print("RTDetrImageProcessor import successful")
except Exception as e:
    print(f"RTDetrImageProcessor import failed: {e}")
