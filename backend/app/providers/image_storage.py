"""
Image Storage Provider
Handles caching of PDF page images to filesystem or Cloud Storage.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path

from common.config import settings  # noqa: F401  secrets/.env の一括ロードを保証
from common.logger import ServiceLogger

log = ServiceLogger("ImageStorage")

_EXT_CONTENT_TYPE: dict[str, str] = {
    "webp": "image/webp",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


class ImageStorageStrategy(ABC):
    def __init__(self):
        self.storage_type = "base"

    @abstractmethod
    def save(
        self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
    ) -> str:
        pass

    async def async_save(
        self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
    ) -> str:
        """非同期でsave()を実行する（イベントループをブロックしない）。"""
        import asyncio

        return await asyncio.to_thread(self.save, file_hash, page_num, image_bytes, ext)

    @abstractmethod
    def get_list(self, file_hash: str) -> list[str]:
        pass

    @abstractmethod
    def delete(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def get_image_bytes(self, image_url: str) -> bytes:
        pass

    def get_gcs_uri(self, image_url: str) -> str | None:
        """GCS URI (gs://bucket/blob) を返す。ローカルストレージでは None。"""
        return None

    def generate_signed_url(
        self, image_url: str, expiration_seconds: int = 900
    ) -> str | None:
        """署名付きURLを生成する。ローカルストレージでは None。"""
        return None

    @abstractmethod
    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        pass

    @abstractmethod
    def get_doc_path(self, file_hash: str) -> str:
        pass

    @abstractmethod
    def get_doc_bytes(self, doc_path: str) -> bytes:
        pass

    def generate_upload_signed_url(
        self, file_hash: str, expiration_seconds: int = 900
    ) -> str | None:
        """PDF PUT 用の署名付き URL を生成する。ローカルストレージでは None。"""
        return None

    def pdf_exists(self, file_hash: str) -> bool:
        """指定ハッシュの PDF がストレージに存在するか確認する。"""
        return False


class LocalImageStorage(ImageStorageStrategy):
    def __init__(self):
        self.images_dir = Path(settings.get("IMAGES_DIR", "src/static/paper_images"))
        self._ensure_dir()
        self.storage_type = "local"

    def _ensure_dir(self):
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
    ) -> str:
        hash_dir = self.images_dir / file_hash
        hash_dir.mkdir(exist_ok=True)

        image_path = hash_dir / f"page_{page_num}.{ext}"
        image_path.write_bytes(image_bytes)

        relative_path = f"/static/paper_images/{file_hash}/page_{page_num}.{ext}"

        return relative_path

    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        doc_dir = self.images_dir.parent / "pdfs"
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_path = doc_dir / f"{file_hash}.pdf"
        doc_path.write_bytes(doc_bytes)
        log.debug("save_doc_local", "PDFをディスクに保存しました", path=str(doc_path))

        return str(doc_path)

    def get_doc_path(self, file_hash: str) -> str:
        doc_dir = self.images_dir.parent / "pdfs"
        path = doc_dir / f"{file_hash}.pdf"
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"PDF not found for hash: {file_hash}")

    def pdf_exists(self, file_hash: str) -> bool:
        doc_dir = self.images_dir.parent / "pdfs"
        return (doc_dir / f"{file_hash}.pdf").exists()

    def get_doc_bytes(self, doc_path: str) -> bytes:
        return Path(doc_path).read_bytes()

    def get_list(self, file_hash: str) -> list[str]:
        hash_dir = self.images_dir / file_hash
        if not hash_dir.exists():
            return []

        def extract_page_num(p):
            try:
                parts = p.stem.split("_")
                if len(parts) == 2 and parts[1].isdigit():
                    return int(parts[1])
                return -1
            except (IndexError, ValueError):
                return -1

        images = []
        seen_page_nums: set[int] = set()
        for ext in ("jpg", "jpeg", "webp"):
            for p in hash_dir.glob(f"page_*.{ext}"):
                num = extract_page_num(p)
                if num >= 0 and num not in seen_page_nums:
                    seen_page_nums.add(num)
                    images.append((num, p))

        # Sort by page number
        images.sort()
        return [f"/static/paper_images/{file_hash}/{img[1].name}" for img in images]

    def delete(self, file_hash: str) -> bool:
        import shutil

        hash_dir = self.images_dir / file_hash
        if hash_dir.exists():
            shutil.rmtree(hash_dir)
            log.info("delete_local", "画像を削除しました", file_hash=file_hash)

            return True

        return False

    def get_image_bytes(self, image_url: str) -> bytes:
        resolved_url = image_url
        if image_url.startswith("http"):
            from urllib.parse import urlparse

            parsed_path = urlparse(image_url).path
            if parsed_path.startswith("/static/paper_images/"):
                resolved_url = parsed_path
            elif len(parsed_path.strip("/").split("/")) == 2:
                # /{hash}/{filename} 形式 → /static/paper_images/{hash}/{filename} に変換
                parts = parsed_path.strip("/").split("/")
                resolved_url = f"/static/paper_images/{parts[0]}/{parts[1]}"

        if resolved_url.startswith("/static/paper_images/"):
            relative_path = resolved_url.replace("/static/paper_images/", "")
            full_path = self.images_dir / relative_path
            if full_path.exists():
                return full_path.read_bytes()
        raise FileNotFoundError(f"Local image not found: {image_url}")


class GCSImageStorage(ImageStorageStrategy):
    def __init__(self):
        from google.cloud import storage

        from app.core.config import get_gcs_bucket_name

        self.bucket_name = get_gcs_bucket_name() or settings.get("STORAGE_BUCKET")
        if not self.bucket_name:
            raise ValueError(
                "Either GCS_BUCKET_NAME / GCS_BUCKET_NAME_STAGING / GCS_BUCKET_NAME_LOCAL "
                "or STORAGE_BUCKET env var is required for GCS storage"
            )
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        self.storage_type = "gcs"
        log.debug(
            "gcs_init", "GCSImageStorageを初期化しました", bucket_name=self.bucket_name
        )

    def save(
        self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
    ) -> str:
        try:
            blob_name = f"paper_images/{file_hash}/page_{page_num}.{ext}"
            blob = self.bucket.blob(blob_name)

            content_type = _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")
            blob.upload_from_string(image_bytes, content_type=content_type)

            # Return a backend-relative URL instead of a GCS direct URL.
            # This avoids CORS/OpaqueResponseBlocking issues in the browser.
            # The frontend prepends API_URL, and the backend serves via /static/paper_images/ proxy.
            relative_path = f"/static/paper_images/{file_hash}/page_{page_num}.{ext}"
            log.debug(
                "save_gcs",
                "ページ画像を保存しました",
                blob_name=blob_name,
                path=relative_path,
            )

            return relative_path

        except Exception as e:
            log.error(
                "save_gcs",
                "GCSへの画像保存中にエラーが発生しました",
                file_hash=file_hash,
                page_num=page_num,
                error=str(e),
                exc_info=True,
            )

            raise

    def get_list(self, file_hash: str) -> list[str]:
        try:
            # GCSからprefix検索
            blobs = self.client.list_blobs(
                self.bucket, prefix=f"paper_images/{file_hash}/"
            )

            def extract_page_num_and_filter(blob):
                try:
                    basename = os.path.basename(blob.name)
                    stem = basename.rsplit(".", 1)[0]
                    parts = stem.split("_")
                    if len(parts) == 2 and parts[1].isdigit():
                        return int(parts[1])
                    return -1
                except Exception:
                    return -1

            _EXT_PRIORITY = {"jpg": 0, "jpeg": 0, "webp": 1}
            seen: dict[int, object] = {}
            seen_priority: dict[int, int] = {}
            for b in blobs:
                ext = os.path.basename(b.name).rsplit(".", 1)[-1].lower()
                if ext not in _EXT_PRIORITY:
                    continue
                num = extract_page_num_and_filter(b)
                if num < 0:
                    continue
                priority = _EXT_PRIORITY[ext]
                if num not in seen or priority < seen_priority[num]:
                    seen[num] = b
                    seen_priority[num] = priority
            blob_list = sorted(seen.items())  # sorted by page_num

            # Return backend-relative URLs (consistent with save())
            urls = []
            for _, blob in blob_list:
                filename = os.path.basename(blob.name)
                relative_url = f"/static/paper_images/{file_hash}/{filename}"
                urls.append(relative_url)

            if urls:
                log.debug(
                    "get_list_gcs",
                    "GCSキャッシュから画像を取得しました",
                    count=len(urls),
                    file_hash=file_hash,
                )

            else:
                log.debug(
                    "get_list_gcs",
                    "GCSキャッシュに画像が見つかりませんでした",
                    file_hash=file_hash,
                )

            return urls
        except Exception as e:
            log.error(
                "get_list_gcs",
                "GCSからの画像一覧取得中にエラーが発生しました",
                file_hash=file_hash,
                error=str(e),
                exc_info=True,
            )

            return []

    def delete(self, file_hash: str) -> bool:
        try:
            blobs = self.client.list_blobs(
                self.bucket, prefix=f"paper_images/{file_hash}/"
            )
            deleted = False
            for blob in blobs:
                blob.delete()
                deleted = True

            if deleted:
                log.debug("delete_gcs", "画像を削除しました", file_hash=file_hash)

            return deleted

        except Exception as e:
            log.error(
                "delete_gcs",
                "GCSからの画像削除中にエラーが発生しました",
                file_hash=file_hash,
                error=str(e),
                exc_info=True,
            )

            return False

    def get_image_bytes(self, image_url: str) -> bytes:
        try:
            if image_url.startswith("/static/"):
                blob_name = image_url.replace("/static/", "", 1)
            elif image_url.startswith("http"):
                from urllib.parse import urlparse

                parsed_path = urlparse(image_url).path
                if parsed_path.startswith("/static/"):
                    # フロントエンドから渡されるフルURL（例: https://worker.paperterrace.page/static/...）
                    # Cloudflare経由の迂回を避け、GCSから直接取得する
                    blob_name = parsed_path.replace("/static/", "", 1)
                elif len(parsed_path.strip("/").split("/")) == 2:
                    # /{hash}/{filename} 形式 → paper_images/{hash}/{filename} に変換
                    parts = parsed_path.strip("/").split("/")
                    blob_name = f"paper_images/{parts[0]}/{parts[1]}"
                else:
                    # 純粋なGCS URLなど: 最終手段としてHTTPフェッチ
                    import requests

                    response = requests.get(image_url, timeout=30)
                    response.raise_for_status()
                    return response.content
            else:
                blob_name = image_url

            blob = self.bucket.blob(blob_name)
            return blob.download_as_bytes()
        except Exception as e:
            log.error(
                "get_image_bytes_gcs",
                "GCSからの画像データ取得中にエラーが発生しました",
                image_url=image_url,
                error=str(e),
                exc_info=True,
            )

            raise

    def _to_blob_name(self, image_url: str) -> str | None:
        """image_url を GCS blob 名に変換する。"""
        if image_url.startswith("/static/"):
            return image_url.replace("/static/", "", 1)
        elif image_url.startswith("http"):
            from urllib.parse import urlparse

            parsed_path = urlparse(image_url).path
            if parsed_path.startswith("/static/"):
                return parsed_path.replace("/static/", "", 1)
            elif len(parsed_path.strip("/").split("/")) == 2:
                parts = parsed_path.strip("/").split("/")
                return f"paper_images/{parts[0]}/{parts[1]}"
        else:
            return image_url
        return None

    def get_gcs_uri(self, image_url: str) -> str | None:
        """image_url から gs://bucket/blob 形式の GCS URI を返す。"""
        result = self.resolve_gcs_uri(image_url)
        return result[0] if result else None

    def resolve_gcs_uri(self, image_url: str) -> tuple[str, str] | None:
        """image_url を解決し (gs://URI, mime_type) を返す。

        Returns:
            (gcs_uri, mime_type) または None
        """
        try:
            blob_name = self._to_blob_name(image_url)
            if not blob_name:
                return None

            blob = self.bucket.blob(blob_name)
            if not blob.exists():
                return None

            ext = blob_name.rsplit(".", 1)[-1].lower()
            mime_type = "image/webp" if ext == "webp" else "image/jpeg"
            return f"gs://{self.bucket_name}/{blob_name}", mime_type
        except Exception as e:
            log.warning(
                "resolve_gcs_uri",
                "GCS URIの解決に失敗しました",
                image_url=image_url,
                error=str(e),
            )
        return None

    def generate_signed_url(
        self, image_url: str, expiration_seconds: int = 900
    ) -> str | None:
        """image_url から署名付きGCS URLを生成する（v4署名、デフォルト15分）。"""
        try:
            blob_name = self._to_blob_name(image_url)
            if not blob_name:
                return None
            import google.auth
            import google.auth.transport.requests
            from datetime import timedelta

            blob = self.bucket.blob(blob_name)

            sign_kwargs: dict = {
                "expiration": timedelta(seconds=expiration_seconds),
                "method": "GET",
                "version": "v4",
            }

            credentials, _ = google.auth.default()
            if not hasattr(credentials, "signer"):
                auth_request = google.auth.transport.requests.Request()
                credentials.refresh(auth_request)
                sign_kwargs["service_account_email"] = credentials.service_account_email
                sign_kwargs["access_token"] = credentials.token

            url = blob.generate_signed_url(**sign_kwargs)
            return url
        except Exception as e:
            log.warning(
                "generate_signed_url",
                "署名付きURLの生成に失敗しました",
                image_url=image_url,
                error=str(e),
            )
            return None

    def generate_upload_signed_url(
        self, file_hash: str, expiration_seconds: int = 900
    ) -> str | None:
        """pdfs/{file_hash}.pdf への PUT 用署名付き URL を生成する（v4署名）。

        Cloud Run / GCE などの ADC 環境では service_account_email と access_token を
        明示的に渡すことで IAM 経由の署名に対応する。
        """
        try:
            import google.auth
            import google.auth.transport.requests
            from datetime import timedelta

            blob = self.bucket.blob(f"pdfs/{file_hash}.pdf")

            sign_kwargs: dict = {
                "expiration": timedelta(seconds=expiration_seconds),
                "method": "PUT",
                "content_type": "application/pdf",
                "version": "v4",
            }

            # ADC 環境（Cloud Run 等）ではキーファイルがないため、
            # アクセストークンとサービスアカウントメールを使って署名する
            credentials, _ = google.auth.default()
            if not hasattr(credentials, "signer"):
                auth_request = google.auth.transport.requests.Request()
                credentials.refresh(auth_request)
                sign_kwargs["service_account_email"] = credentials.service_account_email
                sign_kwargs["access_token"] = credentials.token

            url = blob.generate_signed_url(**sign_kwargs)
            log.debug(
                "generate_upload_signed_url",
                "PUT 用署名付き URL を生成しました",
                file_hash=file_hash,
            )
            return url
        except Exception as e:
            log.warning(
                "generate_upload_signed_url",
                "PUT 署名付き URL の生成に失敗しました",
                file_hash=file_hash,
                error=str(e),
            )
            return None

    def pdf_exists(self, file_hash: str) -> bool:
        """GCS 上に pdfs/{file_hash}.pdf が存在するか確認する。"""
        try:
            return self.bucket.blob(f"pdfs/{file_hash}.pdf").exists()
        except Exception as e:
            log.warning(
                "pdf_exists",
                "GCS 存在確認に失敗しました",
                file_hash=file_hash,
                error=str(e),
            )
            return False

    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        try:
            blob_name = f"pdfs/{file_hash}.pdf"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(doc_bytes, content_type="application/pdf")
            log.debug("save_doc_gcs", "Saved PDF to GCS", blob_name=blob_name)

            return blob_name

        except Exception as e:
            log.error(
                "save_doc_gcs",
                "Error saving PDF to GCS",
                file_hash=file_hash,
                error=str(e),
                exc_info=True,
            )

            raise

    def get_doc_path(self, file_hash: str) -> str:
        # GCSの場合はパスというよりはBlob名
        return f"pdfs/{file_hash}.pdf"

    def get_doc_bytes(self, doc_path: str) -> bytes:
        try:
            blob = self.bucket.blob(doc_path)
            return blob.download_as_bytes()
        except Exception as e:
            log.error(
                "get_doc_bytes_gcs",
                "GCSからのPDFデータ取得中にエラーが発生しました",
                path=doc_path,
                error=str(e),
                exc_info=True,
            )

            raise


# Factory
def get_image_storage() -> ImageStorageStrategy:
    storage_type = str(settings.get("STORAGE_TYPE", "local")).lower()
    if storage_type == "gcs":
        return GCSImageStorage()
    return LocalImageStorage()


# Global instance (lazy init to avoid import errors if env vars missing)
_storage_instance = None


def _get_instance():
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_image_storage()
    return _storage_instance


# 既存APIとの互換レイヤー
def save_page_image(
    file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
) -> str:
    return _get_instance().save(file_hash, page_num, image_bytes, ext)


async def async_save_page_image(
    file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp"
) -> str:
    """非同期でページ画像を保存する（asyncコンテキスト用）。"""
    return await _get_instance().async_save(file_hash, page_num, image_bytes, ext)


def get_page_images(file_hash: str) -> list[str]:
    return _get_instance().get_list(file_hash)


def delete_page_images(file_hash: str) -> bool:
    return _get_instance().delete(file_hash)


def get_image_bytes(image_url: str) -> bytes:
    return _get_instance().get_image_bytes(image_url)


def get_gcs_uri(image_url: str) -> str | None:
    return _get_instance().get_gcs_uri(image_url)


def resolve_gcs_uri(image_url: str) -> tuple[str, str] | None:
    """image_url を解決し (gs://URI, mime_type) を返す。GCS モード以外では None。"""
    inst = _get_instance()
    if not isinstance(inst, GCSImageStorage):
        return None
    return inst.resolve_gcs_uri(image_url)


def get_signed_url(image_url: str, expiration_seconds: int = 900) -> str | None:
    return _get_instance().generate_signed_url(image_url, expiration_seconds)


def get_upload_signed_url(file_hash: str, expiration_seconds: int = 900) -> str | None:
    """PDF PUT 用の署名付き URL を返す。ローカル環境では None。"""
    return _get_instance().generate_upload_signed_url(file_hash, expiration_seconds)


def pdf_blob_exists(file_hash: str) -> bool:
    """指定ハッシュの PDF がストレージに存在するか確認する。"""
    return _get_instance().pdf_exists(file_hash)
