"""
Tests for the translation service.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_translate_word(mock_ai_provider):
    """Test word translation."""
    mock_ai_provider.generate = AsyncMock(return_value="自然言語処理")

    with patch("src.feature.translate.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.translate import TranslationService

        service = TranslationService()
        result = await service.translate_word("NLP", "ja")

        assert result["word"] == "NLP"
        assert result["translation"] == "自然言語処理"
        assert result["target_lang"] == "ja"


@pytest.mark.asyncio
async def test_translate_word_cache(mock_ai_provider):
    """Test that translations are cached."""
    mock_ai_provider.generate = AsyncMock(return_value="翻訳結果")

    with patch("src.feature.translate.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.translate import TranslationService

        service = TranslationService()

        # First call
        await service.translate_word("test", "ja")
        # Second call (should use cache)
        result = await service.translate_word("test", "ja")

        assert result["source"] == "cache"
        assert mock_ai_provider.generate.call_count == 1


@pytest.mark.asyncio
async def test_translate_phrase(mock_ai_provider):
    """Test phrase translation."""
    mock_ai_provider.generate = AsyncMock(return_value="これは翻訳されたフレーズです")

    with patch("src.feature.translate.get_ai_provider", return_value=mock_ai_provider):
        from src.feature.translate import TranslationService

        service = TranslationService()
        result = await service.translate_phrase("This is a phrase", "ja")

        assert result["phrase"] == "This is a phrase"
        assert "翻訳" in result["translation"]


def test_get_supported_languages():
    """Test getting supported languages."""
    with patch("src.feature.translate.get_ai_provider"):
        from src.feature.translate import TranslationService

        service = TranslationService()
        languages = service.get_supported_languages()

        assert "ja" in languages
        assert "en" in languages
        assert "zh" in languages
        assert "ko" in languages
