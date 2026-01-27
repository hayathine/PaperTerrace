"""
AIチャットアシスタント機能を提供するモジュール
論文の内容に基づいて質問に回答する
"""

from src.logger import logger
from src.providers import get_ai_provider


class ChatError(Exception):
    """Chat-specific exception."""

    pass


class ChatService:
    """AI Chat service for paper Q&A and author agent simulation."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.history: list[dict] = []

    async def chat(self, user_message: str, document_context: str = "") -> str:
        """
        Generate a chat response based on user message and document context.

        Args:
            user_message: The user's question or message
            document_context: The paper text for context

        Returns:
            AI-generated response
        """
        # Build conversation history for context
        # The user message is added to history *after* a successful response is generated.
        # For prompt generation, we use the current history + the new user message.
        current_conversation = self.history + [{"role": "user", "content": user_message}]
        history_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation[-5:]]
        )
        history_str = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in current_conversation]
        )  # This will be passed as context to the AI provider

        prompt = f"""あなたは学術論文を読む研究者を支援するAIアシスタントです。
以下の論文の内容を踏まえて、ユーザーの質問に日本語で回答してください。

【論文コンテキスト】
{document_context[:8000] if document_context else "論文が読み込まれていません。"}

【会話履歴】
{history_text}

分かりやすく、簡潔に回答してください。"""

        try:
            logger.debug(
                "Processing chat request",
                extra={"message_length": len(user_message), "history_size": len(self.history)},
            )
            response = await self.ai_provider.generate(prompt, context=history_str)
            response = response.strip()

            if not response:
                logger.warning("Empty chat response received")
                raise ChatError("Empty response from AI")

            # Add to history
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": response})

            # Keep history manageable (last 20 exchanges)
            if len(self.history) > 40:
                self.history = self.history[-40:]
                logger.debug("Chat history trimmed to 40 messages")

            logger.info(
                "Chat response generated",
                extra={"response_length": len(response), "history_size": len(self.history)},
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

    async def author_agent_response(self, question: str, paper_text: str) -> str:
        """
        Simulate the author's perspective to answer questions.

        Args:
            question: The user's question
            paper_text: The full paper text

        Returns:
            Response simulating the author's viewpoint
        """
        prompt = f"""あなたはこの論文の著者です。読者からの質問に、著者の視点で回答してください。

【論文内容】
{paper_text[:10000]}

【読者からの質問】
{question}

著者として、研究の背景、動機、方法論の選択理由などを含めて回答してください。
「私たちは...」「本研究では...」のような一人称で回答してください。"""

        try:
            logger.debug(
                "Generating author agent response",
                extra={"question_length": len(question), "paper_length": len(paper_text)},
            )
            response = await self.ai_provider.generate(prompt)
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
