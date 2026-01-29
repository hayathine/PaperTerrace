"""
Author Agent Feature
Generates a persona based on an author's research history and style,
allowing the user to 'chat' with the author.
"""

from typing import Dict, List

from src.features.research_radar import ResearchRadarService
from src.logger import logger
from src.providers import get_ai_provider


class AuthorAgentService:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.research_service = ResearchRadarService()

    async def generate_author_persona(self, author_name: str, current_paper_title: str) -> str:
        """
        Generate a system instruction that mimics the author's style.
        """
        logger.info(f"Generating persona for author: {author_name}")

        # 1. Consensus APIを使って著者の情報を検索
        author_data = await self.research_service.get_author_profile_and_papers(author_name)

        _ = author_data.get("profile", {})
        papers = author_data.get("papers", [])

        # 論文リストがなければ、シミュレーション用に空リストで進める
        # (AIが名前からある程度推測できる場合もあるため)

        papers_text = ""
        if papers:
            papers_text = "【過去の主要論文】\n" + "\n".join(
                [f"- {p.get('title', 'Untitled')} ({p.get('year', 'Unknown')})" for p in papers[:5]]
            )
        else:
            papers_text = "（著者の詳細な論文リストはAPIから取得できませんでした。一般的なこの分野の研究者として振る舞ってください）"

        # 2. Geminiにペルソナ生成を依頼
        from src.prompts import AUTHOR_PERSONA_PROMPT

        prompt = AUTHOR_PERSONA_PROMPT.format(
            author_name=author_name,
            current_paper_title=current_paper_title,
            papers_text=papers_text,
        )

        persona_instruction = await self.ai_provider.generate(prompt)
        return persona_instruction.strip()

    async def chat_with_author(
        self, message: str, history: List[Dict[str, str]], system_instruction: str
    ) -> str:
        """
        Chat with the generated author persona.
        """
        # 単発呼び出しか、履歴付き呼び出しかは AIProvider の実装による
        # ここでは簡易的に直近のやり取りを含めたプロンプトを構築するか、
        # AIProviderがチャットモードを持っていればそれを使う。
        # 現状の PaperTerrace の AIProvider は generate(prompt) なので、
        # コンテキストにシステムプロンプトを含めて送信する。

        conversation = f"System: {system_instruction}\n\n"
        for msg in history[-5:]:  # 直近5件
            role = msg.get("role", "User")
            content = msg.get("content", "")
            conversation += f"{role}: {content}\n"

        conversation += f"User: {message}\nAuthor:"

        response = await self.ai_provider.generate(conversation)
        return response
