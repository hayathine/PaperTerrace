import os
import shutil

import ctranslate2
from huggingface_hub import snapshot_download
from transformers.models.m2m_100.tokenization_m2m_100 import M2M100Tokenizer

model_id = "facebook/m2m100_418M"
output_dir = "models/m2m100_ct2"

# M2M100Tokenizer has no attribute additional_special_tokens error fix

if not hasattr(M2M100Tokenizer, "additional_special_tokens"):
    M2M100Tokenizer.additional_special_tokens = []


def convert_model():
    if os.path.exists(output_dir):
        print(f"Model already exists at {output_dir}. Skipping conversion.")
        return

    print(f"Downloading and converting {model_id} to CTranslate2 format...")

    # 1. Download model and tokenizer
    model_path = snapshot_download(model_id)

    # 2. Use CTranslate2 converter
    converter = ctranslate2.converters.TransformersConverter(model_path)
    converter.convert(output_dir, quantization="int8", force=True)

    # 3. Copy SentencePiece model for runtime use (without transformers)
    spm_source = os.path.join(model_path, "sentencepiece.bpe.model")
    spm_dest = os.path.join(output_dir, "sentencepiece.bpe.model")
    if os.path.exists(spm_source):
        shutil.copy2(spm_source, spm_dest)
        print(f"Copied SentencePiece model to {spm_dest}")
    else:
        print(f"Warning: SentencePiece model not found at {spm_source}")

    print(f"Conversion finished. Model saved to {output_dir}")


if __name__ == "__main__":
    convert_model()
