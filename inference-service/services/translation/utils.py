"""
言語コードマッピングに関するユーティリティ
"""

# M2M100用の言語コードマッピング
LANG_CODES = {
    "en": "__en__",
    "ja": "__ja__",
    "zh": "__zh__",
    "ko": "__ko__",
    "fr": "__fr__",
    "de": "__de__",
    "es": "__es__",
}

LANG_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


def get_lang_name(lang: str) -> str:
    """ISO 639-1 コードを言語名に変換する。"""
    return LANG_NAMES.get(lang.lower(), lang)


def get_m2m100_lang_code(lang: str) -> str:
    """ISO 639-1 コードを M2M100 用の言語コードに変換する。

    Args:
        lang: ISO 639-1 言語コード (例: "ja", "en")

    Returns:
        M2M100 用の言語コード (例: "__ja__")
    """
    return LANG_CODES.get(lang.lower(), f"__{lang.lower()}__")
