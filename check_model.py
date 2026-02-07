import onnxruntime as ort

model_path = "inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx"
session = ort.InferenceSession(model_path)
print("Inputs:")
for i in session.get_inputs():
    print(f" Name: {i.name}, Shape: {i.shape}")

print("\nOutputs:")
for o in session.get_outputs():
    print(f" Name: {o.name}, Shape: {o.shape}")
