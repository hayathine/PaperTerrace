import os

import dspy

from common.config import settings
from common.logger import get_logger

log = get_logger(__name__)

# setup_dspy() で設定した LM の構築パラメータを保持する。
# create_lm_with_cache() でキャッシュ付き LM を作るために参照する。
_lm_model_name: str = ""
_lm_kwargs: dict = {}


def setup_dspy():
    """Configure DSPy with Vertex AI."""
    global _lm_model_name, _lm_kwargs

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

    langsmith_api_key = settings.get("LANGSMITH_API_KEY", "")
    if langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
        os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        project_name = settings.get("LANGSMITH_PROJECT", "paperterrace")
        os.environ["LANGCHAIN_PROJECT"] = project_name
        os.environ["LANGSMITH_PROJECT"] = project_name
        import litellm
        litellm.success_callback = ["langsmith"]
        log.info("setup_dspy", "LangSmith tracing enabled", project=project_name)

    lm = dspy.LM(model_name, **kwargs)
    dspy.configure(lm=lm)

    _lm_model_name = model_name
    _lm_kwargs = kwargs
    return lm


def create_lm_with_cache(cached_content_name: str) -> dspy.LM:
    """Gemini Context Cache を使う DSPy LM を生成する。

    setup_dspy() で設定したモデル・認証情報をそのまま引き継ぎ、
    cached_content パラメータだけを追加して返す。
    """
    return dspy.LM(
        _lm_model_name or settings.get("DSPY_MODEL", "vertex_ai/gemini-2.5-flash-lite"),
        cached_content=cached_content_name,
        **_lm_kwargs,
    )


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
    log.info("save_dspy_module_to_gcs", "Saved optimized module locally", path=local_path)

    # Try to upload to GCS
    bucket = get_dspy_gcs_bucket()
    if bucket:
        try:
            blob = bucket.blob(f"dspy_models/{filename}")
            blob.upload_from_filename(local_path)
            log.info(
                "save_dspy_module_to_gcs",
                "Uploaded to GCS",
                filename=filename,
                bucket=bucket.name,
            )
        except Exception as e:
            log.warning("save_dspy_module_to_gcs", "Failed to upload to GCS", filename=filename, error=str(e))


def load_dspy_module_from_gcs(module: dspy.Module, filename: str) -> bool:
    """Attempt to load a DSPy module from GCS. Fallback to local if GCS fails."""
    bucket = get_dspy_gcs_bucket()
    local_path = os.path.join(os.getcwd(), filename)

    if bucket:
        try:
            blob = bucket.blob(f"dspy_models/{filename}")
            if blob.exists():
                blob.download_to_filename(local_path)
                log.info("load_dspy_module_from_gcs", "Downloaded from GCS", filename=filename)
                module.load(local_path)
                return True
        except Exception as e:
            log.warning("load_dspy_module_from_gcs", "Failed to download from GCS", filename=filename, error=str(e))

    # Fallback to local file if exists
    if os.path.exists(local_path):
        module.load(local_path)
        log.info("load_dspy_module_from_gcs", "Loaded from local fallback", path=local_path)
        return True

    return False
