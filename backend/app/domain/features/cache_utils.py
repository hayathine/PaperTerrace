"""PDFコンテキストキャッシュのユーティリティ"""

from common.config import settings
from common.logger import logger

PDF_CACHE_KEY_PREFIX = "paper_cache_pdf"
# 全サービスで共有するキャッシュモデル。
# Vertex AI のコンテキストキャッシュはモデルに紐づくため、
# 作成・参照・推論すべてで同一モデルを使用する必要がある。
PDF_CACHE_MODEL: str = settings.get("PDF_CACHE_MODEL", "gemini-2.5-flash-lite")

# システムコンテキストキャッシュ用 Redis キープレフィックス
_SYS_CTX_PREFIX = "system_context_cache"
# システムコンテキストはプロセス内で一度取得したら再利用する（Redis への往復を省く）
_sys_ctx_in_memory: dict[str, str] = {}


async def get_or_create_system_context_cache(
    ai_provider,
    redis,
    model: str,
    lang_name: str = "",
    ttl_minutes: int = 1440,
) -> str | None:
    """
    全タスク共通のシステムコンテキストを Gemini Context Cache に保存・再利用する。

    初回（要約タスクなど最初の DSPy 呼び出し時）に system_context テキストを LLM で生成し、
    Gemini Context Cache に登録して cache_name を Redis に保存する。
    以降は cache_name を返すだけで LLM 呼び出しは発生しない。

    Args:
        ai_provider: AIプロバイダーインスタンス
        redis: RedisService インスタンス
        model: 使用するモデル名（キャッシュはモデルに紐づく）
        lang_name: 対象言語名（キャッシュキーに含める）
        ttl_minutes: キャッシュ TTL（デフォルト 24 時間）

    Returns:
        Gemini Context Cache の cache_name。失敗時は None。
    """
    mem_key = f"{model}:{lang_name}"
    if mem_key in _sys_ctx_in_memory:
        return _sys_ctx_in_memory[mem_key]

    redis_key = f"{_SYS_CTX_PREFIX}:{model}:{lang_name}"
    cache_name = redis.get(redis_key)
    if cache_name:
        _sys_ctx_in_memory[mem_key] = cache_name
        return cache_name

    try:
        # DSPy を使わず直接 LLM で system_context テキストを生成する
        from common.dspy_seed_prompt import SYSTEM_CONTEXT_SEED

        prompt = (
            f"{SYSTEM_CONTEXT_SEED}\n\n"
            f"task_type: all tasks (summarization, chat, translation, recommendation)\n"
            f"lang_name: {lang_name or 'Japanese'}"
        )
        response = await ai_provider.generate(prompt, model=model)
        system_context_text: str = (
            response.get("text", "") if isinstance(response, dict) else str(response or "")
        ).strip()

        if not system_context_text:
            return None

        cache_name = await ai_provider.create_context_cache(
            model=model,
            contents=system_context_text,
            ttl_minutes=ttl_minutes,
        )

        redis.set(redis_key, cache_name, expire=ttl_minutes * 60)
        _sys_ctx_in_memory[mem_key] = cache_name
        return cache_name

    except Exception as e:
        logger.warning(f"システムコンテキストキャッシュの作成に失敗しました: {e}")
        return None


def get_pdf_cache_key(paper_id: str) -> str:
    """モデル固有のPDFキャッシュ用Redisキーを返す。"""
    return f"{PDF_CACHE_KEY_PREFIX}:{PDF_CACHE_MODEL}:{paper_id}"


async def get_or_create_pdf_cache(
    paper_id: str,
    pdf_contents: bytes | str,
    ai_provider,
    redis,
    ttl_minutes: int = 60,
) -> str | None:
    """
    Redisから paper_cache_pdf:{PDF_CACHE_MODEL}:{paper_id} キャッシュ名を取得する。
    存在しない場合は ai_provider でコンテキストキャッシュを新規作成し Redis に保存する。
    失敗した場合は None を返す。

    Args:
        paper_id: 論文ID
        pdf_contents: PDFバイナリ (bytes) または GCS URI (str)
        ai_provider: AIプロバイダーインスタンス
        redis: RedisService インスタンス
        ttl_minutes: キャッシュTTL (分)

    Returns:
        キャッシュ名 (str) または None (失敗時)
    """
    cache_key = get_pdf_cache_key(paper_id)
    cache_name = redis.get(cache_key)
    if cache_name:
        return cache_name

    try:
        cache_name = await ai_provider.create_context_cache(
            model=PDF_CACHE_MODEL,
            contents=pdf_contents,
            ttl_minutes=ttl_minutes,
        )
        redis.set(cache_key, cache_name, expire=ttl_minutes * 60)
        return cache_name
    except Exception as e:
        logger.warning(f"PDFコンテキストキャッシュの作成に失敗しました ({paper_id}): {e}")
        return None
