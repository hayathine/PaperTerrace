from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.features.word_analysis import WordAnalysisService


@pytest.fixture
def word_analysis_service():
    with (
        patch("src.features.word_analysis.get_ai_provider") as mock_ai_req,
        patch("src.features.word_analysis.get_dictionary_provider") as mock_dict_req,
        patch("src.features.word_analysis.RedisService") as mock_redis_cls,
    ):
        mock_ai = AsyncMock()
        mock_ai_req.return_value = mock_ai

        mock_dict = MagicMock()
        mock_dict_req.return_value = mock_dict

        mock_redis = MagicMock()
        mock_redis_cls.return_value = mock_redis

        service = WordAnalysisService()
        yield service, mock_ai, mock_dict, mock_redis


@pytest.mark.asyncio
async def test_lookup_or_translate_memory_cache(word_analysis_service):
    """Test lookup from memory cache."""
    service, _, _, _ = word_analysis_service
    # Pre-populate memory cache
    service.translation_cache["apple"] = "りんご"

    result = await service.lookup_or_translate("apple", "ja")
    assert result["translation"] == "りんご"
    assert result["source"] == "Memory Cache"


@pytest.mark.asyncio
async def test_lookup_or_translate_redis_cache(word_analysis_service):
    """Test lookup from Redis cache."""
    service, _, _, mock_redis = word_analysis_service
    mock_redis.get.return_value = "りんご from redis"

    result = await service.lookup_or_translate("apple", "ja")
    assert result["translation"] == "りんご from redis"
    assert result["source"] == "Redis Cache"
    # Should update memory cache
    assert service.translation_cache["apple"] == "りんご from redis"


@pytest.mark.asyncio
async def test_lookup_or_translate_dictionary(word_analysis_service):
    """Test lookup from dictionary."""
    service, _, mock_dict, mock_redis = word_analysis_service
    mock_redis.get.return_value = None
    mock_dict.lookup.return_value = "Dict Definition"

    result = await service.lookup_or_translate("apple", "ja")
    assert result["translation"] == "Dict Definition"[:500]
    assert result["source"] == "Jamdict"


@pytest.mark.asyncio
async def test_lookup_or_translate_ai(word_analysis_service):
    """Test lookup using AI translation with context."""
    service, mock_ai, mock_dict, mock_redis = word_analysis_service
    mock_redis.get.return_value = None
    mock_dict.lookup.return_value = None
    mock_ai.generate.return_value = "AI Translation"

    result = await service.lookup_or_translate("apple", "ja", context="I ate an apple.")
    assert result["translation"] == "AI Translation"
    assert result["source"] == "Gemini (Context)"

    # Verify redis set
    mock_redis.set.assert_called()


@pytest.mark.asyncio
async def test_batch_translate(word_analysis_service):
    """Test batch translation."""
    service, mock_ai, _, _ = word_analysis_service
    mock_ai.generate.return_value = "apple:りんご\nbanana:バナナ"

    # Make sure cache is empty initially
    service.translation_cache = {}

    result = await service.batch_translate(["apple", "banana"], "ja")
    assert result["apple"] == "りんご"
    assert result["banana"] == "バナナ"

    assert service.translation_cache["apple"] == "りんご"


@pytest.mark.asyncio
async def test_batch_translate_cached(word_analysis_service):
    """Test batch translation skips cached words."""
    service, mock_ai, _, _ = word_analysis_service
    service.translation_cache["apple"] = "りんご"

    mock_ai.generate.return_value = "banana:バナナ"

    # "apple" is cached, so only "banana" should go to AI (impl detail dependent, assuming filtered)

    result = await service.batch_translate(["apple", "banana"], "ja")

    # Note: the result of batch_translate typically returns only what was newly translated OR all requested.
    # Looking at the code: result.update(self.translation_cache) isn't there, it returns `result` which is populated from AI.
    # But wait, let's double check implementation of batch_translate.
    # `words_to_translate = [w for w in words if w not in self.translation_cache]`
    # `result` is populated from AI response.
    # So `batch_translate` returns only *new* translations.

    assert "banana" in result
    assert result["banana"] == "バナナ"
    assert "apple" not in result  # Because it wasn't sentient to AI
