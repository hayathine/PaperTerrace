"""
AIチャットアシスタント機能を提供するモジュール
論文の内容に基づいて質問に回答する
"""



from app.providers import get_ai_provider
from common.config import settings
from common.dspy_utils.modules import ChatModule
from common.dspy_utils.trace import TraceContext, trace_dspy_call
from common.logger import logger
from common.dspy_seed_prompt import (
    CHAT_GENERAL_FROM_PDF_PROMPT,
    CHAT_WITH_FIGURE_PROMPT,
    CORE_SYSTEM_PROMPT,
)
from redis_provider.provider import (
    RedisService,
)  # RedisService now uses in-memory cache


class ChatError(Exception):
    """Chat-specific exception."""

    pass


class ChatService:
    """AI Chat service for paper Q&A."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.redis = RedisService()
        self.model = settings.get("MODEL_CHAT", "gemini-2.5-flash")
        self.cache_ttl_minutes = 60
        self.chat_mod = ChatModule()

    async def chat(
        self,
        user_message: str,
        history: list[dict],
        document_context: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        pdf_input: bytes | str | None = None,
        image_bytes: bytes | None = None,
    ) -> dict | str:
        """
        Generate a chat response based on user message and document context.

        Args:
            user_message: The user's question or message
            history: Conversation history
            document_context: The paper text for context
            target_lang: Output language
            paper_id: 論文ID
            user_id: ユーザーID
            session_id: セッションID
            pdf_input: PDFバイナリデータ または GCS URI (gs://...)
            image_bytes: 図表等の画像データ

        Returns:
            AI-generated response (dict with text, trace_id, and optionally grounding)
        """
        # Build conversation context
        recent_history = history[-10:] if len(history) > 10 else history
        current_conversation = recent_history + [
            {"role": "user", "content": user_message}
        ]
        history_text_for_prompt = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation]
        )

        from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDFキャッシュの確認
            pdf_cache_name = None
            if paper_id:
                pdf_cache_name = self.redis.get(f"paper_cache_pdf:{paper_id}")

            if pdf_input or pdf_cache_name:
                # 初回: キャッシュを作成
                if not pdf_cache_name and pdf_input and paper_id:
                    try:
                        pdf_cache_name = await self.ai_provider.create_context_cache(
                            model=self.model,
                            contents=pdf_input,
                            ttl_minutes=self.cache_ttl_minutes,
                        )
                        self.redis.set(
                            f"paper_cache_pdf:{paper_id}",
                            pdf_cache_name,
                            expire=self.cache_ttl_minutes * 60,
                        )
                    except Exception as e:
                        logger.warning(f"PDFキャッシュ作成失敗 ({paper_id}): {e}")

                prompt = CHAT_GENERAL_FROM_PDF_PROMPT.format(
                    lang_name=lang_name,
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                response_data = await self.ai_provider.generate_with_pdf(
                    prompt,
                    pdf_bytes=pdf_input if (not pdf_cache_name and isinstance(pdf_input, bytes)) else None,
                    cached_content_name=pdf_cache_name,
                    model=self.model,
                )
            elif image_bytes:
                # 画像付きチャット
                logger.debug(
                    "画像を使用したチャットリクエストを処理中",
                    extra={
                        "message_length": len(user_message),
                        "image_size": len(image_bytes),
                    },
                )
                context = document_context if document_context else "No paper context."
                prompt = CHAT_WITH_FIGURE_PROMPT.format(
                    lang_name=lang_name,
                    document_context=context[:10000],
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                response_data = await self.ai_provider.generate_with_image(
                    prompt, image_bytes, "image/jpeg", model=self.model
                )
            else:
                # 従来のテキストベース方式
                logger.debug(
                    "テキストベースのチャットリクエストを処理中",
                    extra={
                        "message_length": len(user_message),
                        "history_size": len(history),
                    },
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
                                cache_key,
                                cache_name,
                                expire=self.cache_ttl_minutes * 60,
                            )
                        except Exception as e:
                            logger.warning(
                                f"コンテキストキャッシュの作成に失敗しました ({paper_id}): {e}"
                            )

                # DSPy version
                res, trace_id = await trace_dspy_call(
                    "ChatModule",
                    "ChatGeneral",
                    self.chat_mod,
                    {
                        "document_context": context[:20000]
                        if not cache_name
                        else "See Context Cache",
                        "history_text": history_text_for_prompt,
                        "user_message": user_message,
                        "user_persona": "Helpful Research Assistant",
                        "lang_name": lang_name,
                    },
                    context=TraceContext(
                        user_id=user_id, session_id=session_id, paper_id=paper_id
                    ),
                )
                response_data = res.answer

            # Handle response with grounding metadata
            if isinstance(response_data, dict):
                response_text = response_data.get("text", "").strip()
                grounding = response_data.get("grounding")
            else:
                response_text = str(response_data or "").strip()
                grounding = None

            if not response_text:
                logger.warning("チャットレスポンスが空です")
                raise ChatError("AIからのレスポンスが空です")

            logger.info(
                "チャットレスポンスを生成しました",
                extra={
                    "response_length": len(response_text),
                    "has_grounding": grounding is not None,
                },
            )

            # 従来の返り値(str)との互換性を保ちつつ、必要に応じてtrace_id等を返すためdict化を検討
            # ただし、呼び出し側が str を期待している箇所が多いので慎重に。
            # 今回は trace_id を含めた dict を返すように統一する（呼び出し側の routers/chat.py を修正）。
            result = {
                "text": response_text,
                "trace_id": trace_id if "trace_id" in locals() else None,
            }
            if grounding:
                result["grounding"] = grounding
            return result
        except ChatError:
            raise
        except Exception as e:
            logger.exception(
                "チャットリクエストに失敗しました",
                extra={"error": str(e), "message_preview": user_message[:50]},
            )
            return {
                "text": f"エラーが発生しました: {str(e)}",
                "trace_id": "error",
            }

    async def chat_stream(
        self,
        user_message: str,
        history: list[dict],
        document_context: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        pdf_bytes: bytes | None = None,
        image_bytes: bytes | None = None,
    ):
        """
        Stream a chat response based on user message and document context.
        Yields tokens as they are generated.
        """
        recent_history = history[-10:] if len(history) > 10 else history
        current_conversation = recent_history + [
            {"role": "user", "content": user_message}
        ]
        history_text_for_prompt = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation]
        )

        from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # Handle PDF Cache
            pdf_cache_name = None
            if paper_id:
                pdf_cache_name = self.redis.get(f"paper_cache_pdf:{paper_id}")

            if pdf_bytes or pdf_cache_name:
                # Cache creation logic (same as in chat method)
                if not pdf_cache_name and pdf_bytes and paper_id:
                    try:
                        pdf_cache_name = await self.ai_provider.create_context_cache(
                            model=self.model,
                            contents=pdf_bytes,
                            ttl_minutes=self.cache_ttl_minutes,
                        )
                        self.redis.set(
                            f"paper_cache_pdf:{paper_id}",
                            pdf_cache_name,
                            expire=self.cache_ttl_minutes * 60,
                        )
                    except Exception:
                        pass

                prompt = CHAT_GENERAL_FROM_PDF_PROMPT.format(
                    lang_name=lang_name,
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                async for token in self.ai_provider.generate_with_pdf_stream(
                    prompt,
                    pdf_bytes=pdf_bytes if not pdf_cache_name else None,
                    cached_content_name=pdf_cache_name,
                    model=self.model,
                ):
                    yield token

            elif image_bytes:
                context = document_context if document_context else "No paper context."
                prompt = CHAT_WITH_FIGURE_PROMPT.format(
                    lang_name=lang_name,
                    document_context=context[:10000],
                    history_text=history_text_for_prompt,
                    user_message=user_message,
                )
                async for token in self.ai_provider.generate_with_image_stream(
                    prompt, image_bytes, "image/jpeg", model=self.model
                ):
                    yield token
            else:
                # Text-based stream (bypass DSPy for now for raw streaming)
                context = document_context if document_context else "No paper loaded."
                cache_name = None
                if paper_id:
                    cache_name = self.redis.get(f"paper_cache:{paper_id}")
                    if not cache_name and len(context) > 2000:
                        try:
                            cache_name = await self.ai_provider.create_context_cache(
                                model=self.model,
                                contents=context,
                                system_instruction=CORE_SYSTEM_PROMPT,
                                ttl_minutes=self.cache_ttl_minutes,
                            )
                            self.redis.set(f"paper_cache:{paper_id}", cache_name, expire=self.cache_ttl_minutes * 60)
                        except Exception:
                            pass

                prompt = f"Context: {context[:20000]}\n\nHistory: {history_text_for_prompt}\n\nUser: {user_message}\n\nAssistant (Output in {lang_name}):"
                async for token in self.ai_provider.generate_stream(
                    prompt,
                    system_instruction=CORE_SYSTEM_PROMPT,
                    cached_content_name=cache_name,
                    model=self.model,
                ):
                    yield token

        except Exception as e:
            logger.exception("chat_stream_failed")
            yield f"Error: {str(e)}"

    async def delete_paper_cache(self, paper_id: str):
        """Delete the context cache for a specific paper."""
        cache_key = f"paper_cache:{paper_id}"
        cache_name = self.redis.get(cache_key)
        if cache_name:
            try:
                await self.ai_provider.delete_context_cache(cache_name)
                self.redis.delete(cache_key)
                logger.info(f"論文 {paper_id} のコンテキストキャッシュを削除しました")
            except Exception as e:
                logger.warning(f"コンテキストキャッシュの削除に失敗しました ({paper_id}): {e}")
