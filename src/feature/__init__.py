"""
Feature package containing all AI-powered analysis services.
"""

from .adversarial import AdversarialReviewService
from .chat import ChatService
from .figure_insight import FigureInsightService
from .paragraph_explain import ParagraphExplainService
from .reserch_radear import ResearchRadarService
from .sidebar import SidebarMemoService
from .summary import SummaryService
from .translate import TranslationService

__all__ = [
    "AdversarialReviewService",
    "ChatService",
    "FigureInsightService",
    "ParagraphExplainService",
    "ResearchRadarService",
    "SidebarMemoService",
    "SummaryService",
    "TranslationService",
]
