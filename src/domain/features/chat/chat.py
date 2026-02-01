"""
AIチャットアシスタント機能を提供するモジュール
論文の内容に基づいて質問に回答する
"""

import os
from typing import Any, Dict, List

from pydantic import BaseModel

from src.core.logger import logger
from src.domain.prompts import (
    CHAT_AUTHOR_PERSONA_PROMPT,
    CHAT_GENERAL_RESPONSE_PROMPT,
    CORE_SYSTEM_PROMPT,
)
from src.infra import get_ai_provider


class ChatError(Exception):
    """Chat-specific exception."""

    pass


class Evidence(BaseModel):
    id: str
    page: int
    text: str


class ChatResponse(BaseModel):
    response: str
    evidence: List[Evidence] = []


class ChatService:
    """AI Chat service for paper Q&A and author agent simulation."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_CHAT", "gemini-2.0-flash")
        self.history: list[dict] = []

    async def chat(
        self, user_message: str, document_context: str = "", target_lang: str = "ja"
    ) -> Dict[str, Any]:
        """
        Generate a chat response based on user message and document context.

        Returns:
            Dict containing 'response' (text) and 'evidence' (list)
        """
        current_conversation = self.history + [{"role": "user", "content": user_message}]
        history_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation[-5:]]
        )

        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        context = document_context if document_context else "No paper loaded."

        prompt = CHAT_GENERAL_RESPONSE_PROMPT.format(
            lang_name=lang_name, document_context=context[:25000], history_text=history_text
        )
        instruction = CORE_SYSTEM_PROMPT.format(lang_name=lang_name)

        try:
            logger.debug(
                "Processing grounded chat request",
                extra={"message_length": len(user_message), "history_size": len(self.history)},
            )

            # Request structured output
            structured_res = await self.ai_provider.generate(
                prompt,
                model=self.model,
                system_instruction=instruction,
                response_model=ChatResponse,
            )

            if not structured_res or not structured_res.response:
                logger.warning("Empty chat response received")
                raise ChatError("Empty response from AI")

            # Add to history (only plain text part)
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": structured_res.response})

            # Keep history manageable
            if len(self.history) > 40:
                self.history = self.history[-40:]

            return structured_res.model_dump()

        except Exception as e:
            logger.exception("Chat request failed")
            return {"response": f"エラーが発生しました: {str(e)}", "evidence": []}

    async def author_agent_response(
        self, question: str, paper_text: str, target_lang: str = "ja"
    ) -> str:
        """
        Simulate the author's perspective to answer questions.

        Args:
            question: The user's question
            paper_text: The full paper text

        Returns:
            Response simulating the author's viewpoint
        """
        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = CHAT_AUTHOR_PERSONA_PROMPT.format(
            lang_name=lang_name, paper_text=paper_text[:20000], question=question
        )

        try:
            logger.debug(
                "Generating author agent response",
                extra={"question_length": len(question), "paper_length": len(paper_text)},
            )
            response = await self.ai_provider.generate(prompt, model=self.model)
            response = response.strip()

            if not response:
                logger.warning("Empty author agent response")
                raise ChatError("Empty response from author agent")

            logger.info(
                "Author agent response generated",
                extra={"response_length": len(response)},
            )
            return response
        except ChatError:
            raise
        except Exception as e:
            logger.exception(
                "Author agent response failed",
                extra={"error": str(e)},
            )
            return f"著者としての回答生成に失敗しました: {str(e)}"

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        logger.info("Chat history cleared")
