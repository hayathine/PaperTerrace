"""
Unit tests for ChatService.
"""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_chat_basic(mock_ai_provider):
    """Test basic chat functionality."""
    with patch("src.features.chat.chat.get_ai_provider", return_value=mock_ai_provider):
        from src.features.chat import ChatService

        service = ChatService()
        response = await service.chat("What is this paper about?", "Sample context")

        assert response == "Mock AI response"
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_chat_history(mock_ai_provider):
    """Test that chat maintains conversation history."""
    with patch("src.features.chat.chat.get_ai_provider", return_value=mock_ai_provider):
        from src.features.chat import ChatService

        service = ChatService()
        await service.chat("First message", "Context")
        await service.chat("Second message", "Context")

        assert len(service.history) == 4  # 2 user + 2 assistant messages


@pytest.mark.asyncio
async def test_author_agent_response(mock_ai_provider):
    """Test author agent simulation."""
    with patch("src.features.chat.chat.get_ai_provider", return_value=mock_ai_provider):
        from src.features.chat import ChatService

        service = ChatService()
        response = await service.author_agent_response(
            "Why did you choose this method?", "Paper text here"
        )

        assert response == "Mock AI response"
        args = mock_ai_provider.generate.call_args[0][0]
        assert "author" in args.lower() or "著者" in args


@pytest.mark.asyncio
async def test_clear_history(mock_ai_provider):
    """Test clearing conversation history."""
    with patch("src.features.chat.chat.get_ai_provider", return_value=mock_ai_provider):
        from src.features.chat import ChatService

        service = ChatService()
        await service.chat("Message", "Context")
        assert len(service.history) > 0

        service.clear_history()
        assert len(service.history) == 0
