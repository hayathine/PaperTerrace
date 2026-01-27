"""
Image Storage Provider
Handles caching of PDF page images to filesystem.
"""

import base64
import os
from pathlib import Path

from ..logger import logger

# 画像保存ディレクトリ
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "src/static/paper_images"))


def ensure_images_dir():
    """画像ディレクトリが存在することを確認"""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def save_page_image(file_hash: str, page_num: int, image_b64: str) -> str:
    """ページ画像を保存し、パスを返す"""
    ensure_images_dir()

    # ファイルハッシュごとのディレクトリ
    hash_dir = IMAGES_DIR / file_hash
    hash_dir.mkdir(exist_ok=True)

    # 画像ファイルパス
    image_path = hash_dir / f"page_{page_num}.png"

    # Base64デコードして保存
    image_bytes = base64.b64decode(image_b64)
    image_path.write_bytes(image_bytes)

    # 相対パスを返す（URLアクセス用）
    relative_path = f"/static/paper_images/{file_hash}/page_{page_num}.png"
    logger.debug(f"Saved page image: {relative_path}")

    return relative_path


def get_page_images(file_hash: str) -> list[str]:
    """ファイルハッシュの全ページ画像パスを取得"""
    hash_dir = IMAGES_DIR / file_hash

    if not hash_dir.exists():
        return []

    # ページ番号順にソート
    images = sorted(hash_dir.glob("page_*.png"), key=lambda p: int(p.stem.split("_")[1]))

    return [f"/static/paper_images/{file_hash}/{img.name}" for img in images]


def delete_page_images(file_hash: str) -> bool:
    """ファイルハッシュの全画像を削除"""
    import shutil

    hash_dir = IMAGES_DIR / file_hash

    if hash_dir.exists():
        shutil.rmtree(hash_dir)
        logger.info(f"Deleted images for hash: {file_hash}")
        return True

    return False
