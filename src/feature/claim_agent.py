"""
Claim Verification Agent Module.
Autonomous agent that verifies claims made in papers against external evidence from the web.
"""

import json
import os

from src.logger import logger
from src.providers import get_ai_provider


class ClaimVerificationService:
    """Service for autonomous claim verification."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_CLAIM", "gemini-2.0-flash")

    async def verify_paragraph(self, paragraph: str, lang: str = "ja") -> dict:
        """
        Verify claims in a paragraph using Web Search.

        Args:
            paragraph: The text to verify.
            lang: Target language for the report.

        Returns:
            Dictionary with 'status' (verified/warning/info) and 'report'.
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = f"""You are an autonomous "Evidence Checker".
Your task is to critically verify the claims made in the following text by cross-referencing with external information (Web Search).

[Target Text]
{paragraph}

[Instructions]
1. Identify the core claims (e.g., "Outperforms SOTA by 10%", "New architecture X").
2. AUTONOMOUSLY SEARCH for these claims online. Look for:
   - Reproducibility reports (GitHub issues, Twitter discussions, Reddit threads).
   - Contradictory papers (Google Scholar).
   - Consensus in the community.
3. Report your findings in {lang_name}.

[Output Format]
Return a JSON object with the following structure:
{{
  "status": "warning" | "verified" | "neutral",
  "summary": "Short summary of the verification result (max 100 chars).",
  "details": "Detailed report citing sources found during search. If reproducible or accepted, mention that. If there are doubts, highlight them clearly.",
  "sources": ["List of URL or source names found (optional)"]
}}

Only output valid JSON.
"""
        try:
            logger.info(f"Verifying paragraph claims with model: {self.model}")

            # Call AI with search enabled
            response = await self.ai_provider.generate(prompt, model=self.model, enable_search=True)

            # Parse JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)
            return data

        except Exception as e:
            logger.error(f"Claim verification failed: {e}")
            return {
                "status": "error",
                "summary": "Verification failed",
                "details": "Could not verify claims due to an error.",
                "sources": [],
            }
