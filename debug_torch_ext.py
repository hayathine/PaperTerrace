import torch

# Find torchvision
import torchvision

print(f"torchvision path: {torchvision.__file__}")

try:
    print("Successfully imported torchvision._C")
except Exception as e:
    print(f"Failed to import torchvision._C: {e}")

try:
    # Try to load the library manually if needed
    from torchvision.extension import _load_library

    _load_library()
    print("Extension library loaded via _load_library")
except Exception as e:
    print(f"Failed to load extension library: {e}")

try:
    print("NMS import successful")
except Exception as e:
    print(f"NMS import failed: {e}")

# Check registered operators
try:
    ops = torch.ops.torchvision.collect_operators()
    print(f"Registered ops: {ops}")
except Exception as e:
    print(f"Failed to collect operators: {e}")
