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
        # Pass empty history list
        response = await service.chat(
            user_message="What is this paper about?", history=[], document_context="Sample context"
        )

        assert response == "Mock AI response"
        mock_ai_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_chat_with_history(mock_ai_provider):
    """Test chat with provided history."""
    with patch("src.features.chat.chat.get_ai_provider", return_value=mock_ai_provider):
        from src.features.chat import ChatService

        service = ChatService()
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        response = await service.chat(
            user_message="Follow up question", history=history, document_context="Context"
        )

        assert response == "Mock AI response"
        # Verify prompt construction includes history
        call_args = mock_ai_provider.generate.call_args[0][0]
        assert "Hello" in call_args
        assert "Hi there" in call_args
        assert "Follow up question" in call_args


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
