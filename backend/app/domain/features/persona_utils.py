from __future__ import annotations


def resolve_user_persona(user_id: str | None, fallback: str) -> str:
    """ユーザーIDからペルソナ文字列を解決する。未生成の場合はフォールバック文字列を返す。"""
    if not user_id:
        return fallback
    try:
        from app.providers import get_storage_provider

        persona = get_storage_provider().get_user_persona(user_id)
        if not persona:
            return fallback

        parts: list[str] = []
        if persona.get("knowledge_level"):
            parts.append(f"Level: {persona['knowledge_level']}")
        if persona.get("interests"):
            parts.append(f"Interests: {persona['interests']}")
        if persona.get("preferred_direction"):
            parts.append(f"Direction: {persona['preferred_direction']}")

        return " | ".join(parts) if parts else fallback
    except Exception:
        return fallback
