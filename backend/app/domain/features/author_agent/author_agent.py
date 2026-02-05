"""
Author Agent Feature
Generates a persona based on an author's research history and style,
allowing the user to 'chat' with the author.
"""

from app.domain.features.research_radar import ResearchRadarService
from app.domain.prompts import AGENT_AUTHOR_PERSONA_PROMPT, CORE_SYSTEM_PROMPT
from app.logger import logger
from app.providers import get_ai_provider


class AuthorAgentService:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.research_service = ResearchRadarService()
        self.model = "gemini-1.5-flash"  # Explicitly set or get from env

    async def generate_author_persona(self, author_name: str, current_paper_title: str) -> str:
        """
        Generate a system instruction that mimics the author's style.
        """
        logger.info(f"Generating persona for author: {author_name}")

        # 1. Consensus APIを使って著者の情報を検索
        author_data = await self.research_service.get_author_profile_and_papers(author_name)

        papers = author_data.get("papers", [])

        papers_text = ""
        if papers:
            papers_text = "【過去の主要論文】\n" + "\n".join(
                [f"- {p.get('title', 'Untitled')} ({p.get('year', 'Unknown')})" for p in papers[:5]]
            )
        else:
            papers_text = "（著者の詳細な論文リストはAPIから取得できませんでした。一般的なこの分野の研究者として振る舞ってください）"

        # 2. Geminiにペルソナ生成を依頼
        prompt = AGENT_AUTHOR_PERSONA_PROMPT.format(
            author_name=author_name,
            current_paper_title=current_paper_title,
            papers_text=papers_text,
        )

        persona_instruction = await self.ai_provider.generate(
            prompt, system_instruction=CORE_SYSTEM_PROMPT
        )
        return persona_instruction.strip()

    async def chat_with_author(
        self,
        message: str,
        history: list[dict[str, str]],
        system_instruction: str,
        pdf_bytes: bytes | None = None,
    ) -> str:
        """
        Chat with the generated author persona.

        Args:
            message: ユーザーからのメッセージ
            history: 会話履歴
            system_instruction: 著者ペルソナの指示
            pdf_bytes: PDFバイナリデータ (PDF直接入力方式)
        """
        # Create prompt with history and persona
        conversation = f"System: {system_instruction}\n\n"
        for msg in history[-5:]:  # Recent 5 messages
            role = msg.get("role", "User")
            content = msg.get("content", "")
            conversation += f"{role}: {content}\n"

        conversation += f"User: {message}\nAuthor:"

        # PDF直接入力方式
        if pdf_bytes:
            logger.info("Chat with author using PDF context")
            response = await self.ai_provider.generate_with_pdf(conversation, pdf_bytes)
        else:
            response = await self.ai_provider.generate(conversation)

        return response
