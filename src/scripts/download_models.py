from transformers import AutoModel, AutoProcessor, RTDetrV2ForObjectDetection


def download_models():
    print("Downloading HuggingFace models...")

    # 1. Heron (Docling)
    heron_model = "ds4sd/docling-layout-heron-101"
    print(f"Downloading {heron_model}...")
    RTDetrV2ForObjectDetection.from_pretrained(heron_model)
    AutoProcessor.from_pretrained(heron_model)

    # 2. Surya models
    surya_models = ["vikp/surya_layout", "vikp/surya_det2", "vikp/surya_rec2"]
    for model_id in surya_models:
        print(f"Downloading {model_id}...")
        AutoModel.from_pretrained(model_id)
        AutoProcessor.from_pretrained(model_id)

    # 3. Translation (M2M100)
    m2m_model = "facebook/m2m100_418M"
    print(f"Downloading {m2m_model}...")
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

    M2M100ForConditionalGeneration.from_pretrained(m2m_model)
    M2M100Tokenizer.from_pretrained(m2m_model)

    print("All models downloaded successfully.")


if __name__ == "__main__":
    download_models()
