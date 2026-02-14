"""
Image Storage Provider
Handles caching of PDF page images to filesystem or Cloud Storage.
"""

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from common.logger import logger

load_dotenv("secrets/.env")


class ImageStorageStrategy(ABC):
    @abstractmethod
    def save(self, file_hash: str, page_num: int | str, image_b64: str) -> str:
        pass

    @abstractmethod
    def get_list(self, file_hash: str) -> list[str]:
        pass

    @abstractmethod
    def delete(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def get_image_bytes(self, image_url: str) -> bytes:
        pass


class LocalImageStorage(ImageStorageStrategy):
    def __init__(self):
        self.images_dir = Path(os.getenv("IMAGES_DIR", "src/static/paper_images"))
        self._ensure_dir()

    def _ensure_dir(self):
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_hash: str, page_num: int | str, image_b64: str) -> str:
        hash_dir = self.images_dir / file_hash
        hash_dir.mkdir(exist_ok=True)

        image_path = hash_dir / f"page_{page_num}.png"
        image_bytes = base64.b64decode(image_b64)
        image_path.write_bytes(image_bytes)

        relative_path = f"/static/paper_images/{file_hash}/page_{page_num}.png"
        logger.debug(f"Saved page image (Local): {relative_path}")
        return relative_path

    def save_doc(self, file_hash: str, doc_bytes: bytes) -> str:
        doc_dir = Path("src/static/pdfs")
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_path = doc_dir / f"{file_hash}.pdf"
        doc_path.write_bytes(doc_bytes)
        return str(doc_path)

    def get_doc_path(self, file_hash: str) -> str:
        path = Path(f"src/static/pdfs/{file_hash}.pdf")
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"PDF not found for hash: {file_hash}")

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
        for p in hash_dir.glob("page_*.png"):
            num = extract_page_num(p)
            if num >= 0:
                images.append((num, p))

        # Sort by page number
        images.sort()
        return [f"/static/paper_images/{file_hash}/{img[1].name}" for img in images]

    def delete(self, file_hash: str) -> bool:
        import shutil

        hash_dir = self.images_dir / file_hash
        if hash_dir.exists():
            shutil.rmtree(hash_dir)
            logger.info(f"Deleted images (Local) for hash: {file_hash}")
            return True
        return False

    def get_image_bytes(self, image_url: str) -> bytes:
        # e.g., /static/paper_images/HASH/page_1.png
        if image_url.startswith("/static/paper_images/"):
            relative_path = image_url.replace("/static/paper_images/", "")
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

    def save(self, file_hash: str, page_num: int | str, image_b64: str) -> str:
        blob_name = f"paper_images/{file_hash}/page_{page_num}.png"
        blob = self.bucket.blob(blob_name)

        image_bytes = base64.b64decode(image_b64)
        blob.upload_from_string(image_bytes, content_type="image/png")

        # Cloud Run等では署名付きURLか、公開URLか、アプリ経由で配信するか考慮が必要
        # ここでは単純に公開URLに近い形か、あるいはプロキシ用のパスを返す
        # GCSの画像に直接アクセスさせるなら公開設定が必要だが、セキュリティ上アプリ経由が望ましい場合も。
        # 今回はシンプルに、アプリがプロキシするためのパスルールに合わせるか、
        # あるいは GCS の Media Link を使うか。
        # PaperTerraceの現状の実装では /static/... でアクセスしているため、
        # 本番では /static/ のマッピングを変えるか、署名付きURLを払い出すのが良い。

        # 署名付きURLを発行して画像にアクセス可能にする
        # Cloud Run環境では静的ファイルの配信に制限があるため、
        # GCSの署名付きURLを使用してクライアントが直接アクセスできるようにする
        import datetime

        # 環境によってCredentialsに秘密鍵が含まれない場合があるため、
        # IAM API経由で署名を行うように明示的に指定する
        try:
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(hours=12),
                method="GET",
                service_account_email=self.client.get_service_account_email(),
            )
        except Exception as e:
            logger.warning(
                f"Failed to generate signed URL using IAM, falling back: {e}"
            )
            # 署名付きURLが使えない場合のフォールバック（アクセストークンの有無などに依存）
            url = blob.public_url

        logger.debug(f"Saved page image (GCS): {blob_name}")
        return url

    def get_list(self, file_hash: str) -> list[str]:
        # GCSからprefix検索
        blobs = self.client.list_blobs(self.bucket, prefix=f"paper_images/{file_hash}/")

        # ページ順にソートしたい
        # page_1.png, page_2.png...
        def extract_page_num_and_filter(blob):
            try:
                basename = os.path.basename(blob.name).replace(".png", "")
                parts = basename.split("_")
                if len(parts) == 2 and parts[1].isdigit():
                    return int(parts[1])
                return -1
            except Exception:
                return -1

        blob_list = []
        for b in blobs:
            num = extract_page_num_and_filter(b)
            if num >= 0:
                blob_list.append((num, b))

        blob_list.sort()

        urls = []
        import datetime

        for _, blob in blob_list:
            # 署名付きURL生成
            try:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=12),
                    method="GET",
                    service_account_email=self.client.get_service_account_email(),
                )
            except Exception as e:
                logger.warning(f"Failed to generate signed URL for list result: {e}")
                url = blob.public_url
            urls.append(url)

        return urls

    def delete(self, file_hash: str) -> bool:
        blobs = self.client.list_blobs(self.bucket, prefix=f"paper_images/{file_hash}/")
        deleted = False
        for blob in blobs:
            blob.delete()
            deleted = True

        if deleted:
            logger.info(f"Deleted images (GCS) for hash: {file_hash}")
        return deleted

    def get_image_bytes(self, image_url: str) -> bytes:
        # GCSの場合、URLから直接取得するか、URLをパースしてBlobとして取得する
        # ここではシンプルにrequestsでURLから取得する（署名付きURLならアクセス可能）
        import requests

        response = requests.get(image_url)
        response.raise_for_status()
        return response.content


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
def save_page_image(file_hash: str, page_num: int | str, image_b64: str) -> str:
    return _get_instance().save(file_hash, page_num, image_b64)


def get_page_images(file_hash: str) -> list[str]:
    return _get_instance().get_list(file_hash)


def delete_page_images(file_hash: str) -> bool:
    return _get_instance().delete(file_hash)


def get_image_bytes(image_url: str) -> bytes:
    return _get_instance().get_image_bytes(image_url)
