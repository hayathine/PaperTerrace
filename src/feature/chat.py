"""
生成AIを用いてチャット機能を提供するモジュール
著者エージェントの基盤としても利用
"""

from src.logger import logger
from src.providers import get_ai_provider


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
        self.history.append({"role": "user", "content": user_message})

        # Build conversation history for context
        history_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in self.history[-5:]]
        )

        prompt = f"""あなたは学術論文を読む研究者を支援するAIアシスタントです。
以下の論文の内容を踏まえて、ユーザーの質問に日本語で回答してください。

【論文コンテキスト】
{document_context[:8000] if document_context else "論文が読み込まれていません。"}

【会話履歴】
{history_text}

分かりやすく、簡潔に回答してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            self.history.append({"role": "assistant", "content": response})
            logger.info("Chat response generated")
            return response
        except Exception as e:
            logger.error(f"Chat generation failed: {e}")
            return f"エラーが発生しました: {str(e)}"

    async def author_agent_response(
        self, question: str, paper_text: str
    ) -> str:
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
            response = await self.ai_provider.generate(prompt)
            logger.info("Author agent response generated")
            return response
        except Exception as e:
            logger.error(f"Author agent generation failed: {e}")
            return f"エラーが発生しました: {str(e)}"

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        logger.info("Chat history cleared")
