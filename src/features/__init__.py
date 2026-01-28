"""
Feature package containing all AI-powered analysis services.
"""

from .adversarial import AdversarialReviewService
from .chat import ChatService
from .cite_intent import CiteIntentService
from .claim_agent import ClaimVerificationService
from .figure_insight import FigureInsightService
from .paragraph_explain import ParagraphExplainService
from .research_radar import ResearchRadarService
from .sidebar import SidebarNoteService
from .summary import SummaryService
from .translate import TranslationService

__all__ = [
    "AdversarialReviewService",
    "ChatService",
    "CiteIntentService",
    "ClaimVerificationService",
    "FigureInsightService",
    "ParagraphExplainService",
    "ResearchRadarService",
    "SidebarNoteService",
    "SummaryService",
    "TranslationService",
]
