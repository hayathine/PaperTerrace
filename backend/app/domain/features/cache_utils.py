"""PDFコンテキストキャッシュのユーティリティ"""

from common.logger import logger

PDF_CACHE_KEY_PREFIX = "paper_cache_pdf"


async def get_or_create_pdf_cache(
    paper_id: str,
    pdf_contents: bytes | str,
    ai_provider,
    redis,
    model: str,
    ttl_minutes: int = 60,
) -> str | None:
    """
    Redisから paper_cache_pdf:{paper_id} キャッシュ名を取得する。
    存在しない場合は ai_provider でコンテキストキャッシュを新規作成し Redis に保存する。
    失敗した場合は None を返す。

    Args:
        paper_id: 論文ID
        pdf_contents: PDFバイナリ (bytes) または GCS URI (str)
        ai_provider: AIプロバイダーインスタンス
        redis: RedisService インスタンス
        model: 使用するモデル名
        ttl_minutes: キャッシュTTL (分)

    Returns:
        キャッシュ名 (str) または None (失敗時)
    """
    cache_key = f"{PDF_CACHE_KEY_PREFIX}:{paper_id}"
    cache_name = redis.get(cache_key)
    if cache_name:
        return cache_name

    try:
        cache_name = await ai_provider.create_context_cache(
            model=model,
            contents=pdf_contents,
            ttl_minutes=ttl_minutes,
        )
        redis.set(cache_key, cache_name, expire=ttl_minutes * 60)
        return cache_name
    except Exception as e:
        logger.warning(f"PDFコンテキストキャッシュの作成に失敗しました ({paper_id}): {e}")
        return None
