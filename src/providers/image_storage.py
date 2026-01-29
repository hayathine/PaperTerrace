"""
Image Storage Provider
Handles caching of PDF page images to filesystem or Cloud Storage.
"""

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from ..logger import logger

load_dotenv()


class ImageStorageStrategy(ABC):
    @abstractmethod
    def save(self, file_hash: str, page_num: int | str, image_b64: str) -> str:
        pass

    @abstractmethod
    def get_list(self, file_hash: str) -> List[str]:
        pass

    @abstractmethod
    def delete(self, file_hash: str) -> bool:
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

    def get_list(self, file_hash: str) -> List[str]:
        hash_dir = self.images_dir / file_hash
        if not hash_dir.exists():
            return []

        images = sorted(hash_dir.glob("page_*.png"), key=lambda p: int(p.stem.split("_")[1]))
        return [f"/static/paper_images/{file_hash}/{img.name}" for img in images]

    def delete(self, file_hash: str) -> bool:
        import shutil

        hash_dir = self.images_dir / file_hash
        if hash_dir.exists():
            shutil.rmtree(hash_dir)
            logger.info(f"Deleted images (Local) for hash: {file_hash}")
            return True
        return False


class GCSImageStorage(ImageStorageStrategy):
    def __init__(self):
        from google.cloud import storage

        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME env var is required for GCS storage type")
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

        # 簡易実装: 署名付きURLを発行する (有効期限1時間など)
        # ただし頻繁に発行すると遅いので、理想は Load Balancer + CDN
        # ここでは取り急ぎ authenticated URL を返すか、リダイレクト用パスを返す

        # FIXME: Cloud Run 上で static files として扱うには工夫が必要。
        # 一旦、署名付きURLを返す実装にする（クライアントはそれをimg srcにする）
        # ただし、現状のフロントエンドは /static/... を期待している箇所があるかもしれない。

        # 既存互換性重視:
        # フロントエンドがそのまま表示できるよう、署名付きURLを返す
        import datetime

        url = blob.generate_signed_url(
            version="v4", expiration=datetime.timedelta(hours=12), method="GET"
        )

        logger.debug(f"Saved page image (GCS): {blob_name}")
        return url

    def get_list(self, file_hash: str) -> List[str]:
        # GCSからprefix検索
        blobs = self.client.list_blobs(self.bucket, prefix=f"paper_images/{file_hash}/")

        # ページ順にソートしたい
        # page_1.png, page_2.png...
        blob_list = list(blobs)

        def extract_page_num(blob):
            try:
                # paper_images/{hash}/page_{num}.png
                basename = os.path.basename(blob.name)
                return int(basename.split("_")[1].split(".")[0])
            except (IndexError, ValueError):
                return 0

        blob_list.sort(key=extract_page_num)

        urls = []
        import datetime

        for blob in blob_list:
            # 署名付きURL生成（キャッシュなどを考慮すると非効率だが一旦これで）
            url = blob.generate_signed_url(
                version="v4", expiration=datetime.timedelta(hours=12), method="GET"
            )
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


def get_page_images(file_hash: str) -> List[str]:
    return _get_instance().get_list(file_hash)


def delete_page_images(file_hash: str) -> bool:
    return _get_instance().delete(file_hash)
