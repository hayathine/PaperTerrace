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
    "png": "image/png",
}


class ImageStorageStrategy(ABC):
    def __init__(self):
        self.storage_type = "base"

    @abstractmethod
    def save(self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
        pass

    async def async_save(self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
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

    @abstractmethod
    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        pass

    @abstractmethod
    def get_doc_path(self, file_hash: str) -> str:
        pass

    @abstractmethod
    def get_doc_bytes(self, doc_path: str) -> bytes:
        pass


class LocalImageStorage(ImageStorageStrategy):
    def __init__(self):
        self.images_dir = Path(os.getenv("IMAGES_DIR", "src/static/paper_images"))
        self._ensure_dir()
        self.storage_type = "local"

    def _ensure_dir(self):
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
        hash_dir = self.images_dir / file_hash
        hash_dir.mkdir(exist_ok=True)

        image_path = hash_dir / f"page_{page_num}.{ext}"
        image_path.write_bytes(image_bytes)

        relative_path = f"/static/paper_images/{file_hash}/page_{page_num}.{ext}"
        log.debug("save_local", "Saved page image", path=relative_path)

        return relative_path

    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        doc_dir = self.images_dir.parent / "pdfs"
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_path = doc_dir / f"{file_hash}.pdf"
        doc_path.write_bytes(doc_bytes)
        log.debug("save_doc_local", "Saved PDF to disk", path=str(doc_path))

        return str(doc_path)

    def get_doc_path(self, file_hash: str) -> str:
        doc_dir = self.images_dir.parent / "pdfs"
        path = doc_dir / f"{file_hash}.pdf"
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"PDF not found for hash: {file_hash}")

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
        # WebP優先（新形式）、次にPNG（旧形式・移行期対応）
        seen_page_nums: set[int] = set()
        for ext in ("webp", "png"):
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
            log.info("delete_local", "Deleted images", file_hash=file_hash)

            return True

        return False

    def get_image_bytes(self, image_url: str) -> bytes:
        # e.g., /static/paper_images/HASH/page_1.png
        # フロントエンドから渡されるフルURL (https://worker.example.com/...) も正規化して処理する
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

        self.bucket_name = os.getenv("GCS_BUCKET_NAME") or os.getenv("STORAGE_BUCKET")
        if not self.bucket_name:
            raise ValueError(
                "Either GCS_BUCKET_NAME or STORAGE_BUCKET env var is required for GCS storage"
            )
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        self.storage_type = "gcs"
        log.debug(
            "gcs_init", "GCSImageStorage initialized", bucket_name=self.bucket_name
        )

    def save(self, file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
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
                "save_gcs", "Saved page image", blob_name=blob_name, path=relative_path
            )

            return relative_path

        except Exception as e:
            log.error(
                "save_gcs",
                "Error saving image to GCS",
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

            # ページ順にソートしたい
            # page_1.png, page_2.png...
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

            # WebP優先（新形式）、次にPNG（旧形式・移行期対応）
            seen: dict[int, object] = {}
            for b in blobs:
                ext = os.path.basename(b.name).rsplit(".", 1)[-1].lower()
                if ext not in ("webp", "png"):
                    continue
                num = extract_page_num_and_filter(b)
                if num < 0:
                    continue
                if num not in seen or ext == "webp":
                    seen[num] = b
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
                    "Retrieved images from GCS cache",
                    count=len(urls),
                    file_hash=file_hash,
                )

            else:
                log.debug(
                    "get_list_gcs", "No images found in GCS cache", file_hash=file_hash
                )

            return urls
        except Exception as e:
            log.error(
                "get_list_gcs",
                "Error listing images from GCS",
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
                log.debug("delete_gcs", "Deleted images", file_hash=file_hash)

            return deleted

        except Exception as e:
            log.error(
                "delete_gcs",
                "Error deleting images from GCS",
                file_hash=file_hash,
                error=str(e),
                exc_info=True,
            )

            return False

    def get_image_bytes(self, image_url: str) -> bytes:
        try:
            # Convert relative URL back to GCS blob name
            # /static/paper_images/{hash}/page_{num}.png -> paper_images/{hash}/page_{num}.png
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
                "Error getting image bytes from GCS",
                image_url=image_url,
                error=str(e),
                exc_info=True,
            )

            raise

    def get_gcs_uri(self, image_url: str) -> str | None:
        """image_url から gs://bucket/blob 形式の GCS URI を返す。"""
        try:
            blob_name: str | None = None
            if image_url.startswith("/static/"):
                blob_name = image_url.replace("/static/", "", 1)
            elif image_url.startswith("http"):
                from urllib.parse import urlparse

                parsed_path = urlparse(image_url).path
                if parsed_path.startswith("/static/"):
                    blob_name = parsed_path.replace("/static/", "", 1)
                elif len(parsed_path.strip("/").split("/")) == 2:
                    parts = parsed_path.strip("/").split("/")
                    blob_name = f"paper_images/{parts[0]}/{parts[1]}"
            else:
                blob_name = image_url

            if blob_name:
                return f"gs://{self.bucket_name}/{blob_name}"
        except Exception as e:
            log.warning("get_gcs_uri", "Failed to build GCS URI", image_url=image_url, error=str(e))
        return None

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
                "Error getting PDF bytes from GCS",
                path=doc_path,
                error=str(e),
                exc_info=True,
            )

            raise


# Factory
def get_image_storage() -> ImageStorageStrategy:
    storage_type = os.getenv("STORAGE_TYPE", "local").lower()
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
def save_page_image(file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
    return _get_instance().save(file_hash, page_num, image_bytes, ext)


async def async_save_page_image(file_hash: str, page_num: int | str, image_bytes: bytes, ext: str = "webp") -> str:
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
