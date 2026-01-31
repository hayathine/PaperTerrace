"""
AIチャットアシスタント機能を提供するモジュール
論文の内容に基づいて質問に回答する
"""

import os

from src.logger import logger
from src.prompts import (
    CHAT_AUTHOR_FROM_PDF_PROMPT,
    CHAT_AUTHOR_PERSONA_PROMPT,
    CHAT_GENERAL_FROM_PDF_PROMPT,
    CHAT_GENERAL_RESPONSE_PROMPT,
    CHAT_WITH_FIGURE_PROMPT,
    CORE_SYSTEM_PROMPT,
)
from src.providers import get_ai_provider
from src.providers.redis_provider import RedisService


class ChatError(Exception):
    """Chat-specific exception."""

    pass


class ChatService:
    """AI Chat service for paper Q&A and author agent simulation."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.redis = RedisService()
        self.model = os.getenv("MODEL_CHAT", "gemini-2.0-flash")
        self.cache_ttl_minutes = 60
        # History is now managed by the router/caller via Redis

    async def chat(
        self,
        user_message: str,
        history: list[dict],
        document_context: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        pdf_bytes: bytes | None = None,
        image_bytes: bytes | None = None,
    ) -> str:
        """
        Generate a chat response based on user message and document context.

        Args:
            user_message: The user's question or message
            history: Conversation history (list of role/content dicts)
            document_context: The paper text for context
            target_lang: Output language
            paper_id: 論文ID (キャッシュ管理用)
            pdf_bytes: PDFバイナリデータ (PDF直接入力方式)
            image_bytes: 図表等の画像データ

        Returns:
            AI-generated response
        """
        # Build conversation context
        recent_history = history[-10:] if len(history) > 10 else history
        current_conversation = recent_history + [{"role": "user", "content": user_message}]
        history_text_for_prompt = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation]
        )

        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDF直接入力方式
            if pdf_bytes:
                logger.debug(
                    "Processing chat request with PDF",
                    extra={"message_length": len(user_message), "pdf_size": len(pdf_bytes)},
                )
                prompt = CHAT_GENERAL_FROM_PDF_PROMPT.format(
                    lang_name=lang_name,
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                response = await self.ai_provider.generate_with_pdf(
                    prompt, pdf_bytes, model=self.model
                )
            elif image_bytes:
                # 画像付きチャット
                logger.debug(
                    "Processing chat request with image",
                    extra={"message_length": len(user_message), "image_size": len(image_bytes)},
                )
                context = document_context if document_context else "No paper context."
                prompt = CHAT_WITH_FIGURE_PROMPT.format(
                    lang_name=lang_name,
                    document_context=context[:10000],
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                response = await self.ai_provider.generate_with_image(
                    prompt, image_bytes, "image/png", model=self.model
                )
            else:
                # 従来のテキストベース方式
                logger.debug(
                    "Processing chat request with text",
                    extra={"message_length": len(user_message), "history_size": len(history)},
                )
                context = document_context if document_context else "No paper loaded."

                # チャッシュの活用
                cache_name = None
                if paper_id:
                    cache_key = f"paper_cache:{paper_id}"
                    cache_name = self.redis.get(cache_key)

                    if not cache_name and len(context) > 2000:
                        # キャッシュを作成 (コンテキストがある程度大きい場合のみ)
                        try:
                            cache_name = await self.ai_provider.create_context_cache(
                                model=self.model,
                                contents=context,
                                system_instruction=CORE_SYSTEM_PROMPT,
                                ttl_minutes=self.cache_ttl_minutes,
                            )
                            self.redis.set(
                                cache_key, cache_name, expire=self.cache_ttl_minutes * 60
                            )
                        except Exception as e:
                            logger.warning(f"Failed to create context cache for {paper_id}: {e}")

                prompt = CHAT_GENERAL_RESPONSE_PROMPT.format(
                    lang_name=lang_name,
                    document_context=context[:20000] if not cache_name else "See Context Cache",
                    history_text=history_text_for_prompt,
                    user_message=user_message,  # Added
                )

                response = await self.ai_provider.generate(
                    prompt,
                    model=self.model,
                    system_instruction=CORE_SYSTEM_PROMPT,
                    cached_content_name=cache_name,
                )

            response = response.strip()

            if not response:
                logger.warning("Empty chat response received")
                raise ChatError("Empty response from AI")

            logger.info(
                "Chat response generated",
                extra={"response_length": len(response)},
            )
            return response
        except ChatError:
            raise
        except Exception as e:
            logger.exception(
                "Chat request failed",
                extra={"error": str(e), "message_preview": user_message[:50]},
            )
            return f"エラーが発生しました: {str(e)}"

    async def author_agent_response(
        self,
        question: str,
        paper_text: str = "",
        target_lang: str = "ja",
        pdf_bytes: bytes | None = None,
    ) -> str:
        """
        Simulate the author's perspective to answer questions.

        Args:
            question: The user's question
            paper_text: The full paper text (従来のテキストベース)
            target_lang: Output language
            pdf_bytes: PDFバイナリデータ (PDF直接入力方式)

        Returns:
            Response simulating the author's viewpoint
        """
        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDF直接入力方式
            if pdf_bytes:
                logger.debug(
                    "Generating author agent response from PDF",
                    extra={"question_length": len(question), "pdf_size": len(pdf_bytes)},
                )
                prompt = CHAT_AUTHOR_FROM_PDF_PROMPT.format(lang_name=lang_name, question=question)
                response = await self.ai_provider.generate_with_pdf(
                    prompt, pdf_bytes, model=self.model
                )
            else:
                # 従来のテキストベース方式
                logger.debug(
                    "Generating author agent response from text",
                    extra={"question_length": len(question), "paper_length": len(paper_text)},
                )
                prompt = CHAT_AUTHOR_PERSONA_PROMPT.format(
                    lang_name=lang_name, paper_text=paper_text[:20000], question=question
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

    async def delete_paper_cache(self, paper_id: str):
        """Delete the context cache for a specific paper."""
        cache_key = f"paper_cache:{paper_id}"
        cache_name = self.redis.get(cache_key)
        if cache_name:
            try:
                await self.ai_provider.delete_context_cache(cache_name)
                self.redis.delete(cache_key)
                logger.info(f"Deleted context cache for paper {paper_id}")
            except Exception as e:
                logger.warning(f"Failed to delete context cache for {paper_id}: {e}")
