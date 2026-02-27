import os

import dspy


def setup_dspy():
    """Configure DSPy with Gemini."""
    # Use gemini/ prefix for litellm
    model_name = os.environ.get("DSPY_GEMINI_MODEL", "gemini/gemini-1.5-flash")
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        lm = dspy.LM(model_name, api_key=api_key)
        dspy.configure(lm=lm)
        return lm
    else:
        print("GEMINI_API_KEY is not set. DSPy not fully configured.")
        lm = dspy.LM(model_name)
        dspy.configure(lm=lm)
        return lm


def get_dspy_gcs_bucket():
    from google.cloud import storage

    bucket_name = os.getenv("GCS_BUCKET_NAME") or os.getenv("STORAGE_BUCKET")
    if not bucket_name:
        return None
    client = storage.Client()
    return client.bucket(bucket_name)


def save_dspy_module_to_gcs(module: dspy.Module, filename: str):
    """Save the optimized DSPy module to GCS and locally."""
    # Always save locally first
    local_path = os.path.join(os.getcwd(), filename)
    module.save(local_path)
    print(f"✅ Saved optimized module locally to {local_path}")

    # Try to upload to GCS
    bucket = get_dspy_gcs_bucket()
    if bucket:
        try:
            blob = bucket.blob(f"dspy_models/{filename}")
            blob.upload_from_filename(local_path)
            print(
                f"✅ Uploaded {filename} to GCS (gs://{bucket.name}/dspy_models/{filename})"
            )
        except Exception as e:
            print(f"⚠️ Failed to upload {filename} to GCS: {e}")


def load_dspy_module_from_gcs(module: dspy.Module, filename: str) -> bool:
    """Attempt to load a DSPy module from GCS. Fallback to local if GCS fails."""
    bucket = get_dspy_gcs_bucket()
    local_path = os.path.join(os.getcwd(), filename)

    if bucket:
        try:
            blob = bucket.blob(f"dspy_models/{filename}")
            if blob.exists():
                blob.download_to_filename(local_path)
                print(f"✅ Downloaded {filename} from GCS")
                module.load(local_path)
                return True
        except Exception as e:
            print(f"⚠️ Failed to download {filename} from GCS: {e}")

    # Fallback to local file if exists
    if os.path.exists(local_path):
        module.load(local_path)
        print(f"✅ Loaded optimized module from local fallback '{local_path}'")
        return True

    return False
