import os

import dspy

from common.config import settings


def setup_dspy():
    """Configure DSPy with Vertex AI."""
    # Use vertex_ai/ prefix for litellm
    model_name = settings.get("DSPY_MODEL", "vertex_ai/gemini-2.5-flash-lite")
    project = settings.get("GCP_PROJECT_ID")
    location = settings.get("GCP_LOCATION", "us-central1")
    credentials = settings.get("GOOGLE_APPLICATION_CREDENTIALS")

    kwargs: dict = {}
    if project:
        kwargs["vertex_project"] = project
    if location:
        kwargs["vertex_location"] = location
    if credentials:
        kwargs["vertex_credentials"] = credentials

    lm = dspy.LM(model_name, **kwargs)
    dspy.configure(lm=lm)
    return lm


def get_dspy_gcs_bucket():
    from google.cloud import storage

    bucket_name = settings.get("GCS_BUCKET_NAME") or settings.get("STORAGE_BUCKET")
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
