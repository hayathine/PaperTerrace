import dspy

from common.dspy.signatures import (
    AdversarialCritique,
    ChatAuthorPersona,
    ChatGeneral,
    ContextAwareTranslation,
    PaperRecommendation,
    PaperSummary,
    PaperSummaryContext,
    PaperSummarySections,
    UserProfileEstimation,
    VisionAnalyzeFigure,
)


class UserProfileModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.estimate = dspy.Predict(UserProfileEstimation)

    def forward(self, paper_summary: str, conversation_history: str, word_clicks: str):
        result = self.estimate(
            paper_summary=paper_summary,
            conversation_history=conversation_history,
            word_clicks=word_clicks,
        )
        dspy.Assert(
            result.knowledge_level in ["初級", "中級", "上級"],
            "Knowledge level must be 初級/中級/上級",
        )
        return result


class RecommendationModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.recommend = dspy.ChainOfThought(PaperRecommendation)

    def forward(
        self,
        paper_analysis: str,
        knowledge_level: str,
        interests: str,
        unknown_concepts: str,
        preferred_direction: str,
    ):
        result = self.recommend(
            paper_analysis=paper_analysis,
            knowledge_level=knowledge_level,
            interests=interests,
            unknown_concepts=unknown_concepts,
            preferred_direction=preferred_direction,
        )

        # Mandatory Constraints
        dspy.Assert(len(result.recommendations) >= 3, "推薦は3件以上必要")
        dspy.Assert(len(result.search_queries) >= 2, "検索クエリは2件以上必要")

        # Soft Constraints
        lowercase_recs = [r.lower() for r in result.recommendations]
        dspy.Suggest(
            knowledge_level != "初級" or any("survey" in r for r in lowercase_recs),
            "初級ユーザーにはsurvey論文を含めることを推奨",
        )

        return result


class PaperSummaryModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict(PaperSummary)

    def forward(self, paper_text: str, lang_name: str):
        return self.summarize(paper_text=paper_text, lang_name=lang_name)


class SectionSummaryModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict(PaperSummarySections)

    def forward(self, paper_text: str, lang_name: str):
        return self.summarize(paper_text=paper_text, lang_name=lang_name)


class AdversarialModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.critique = dspy.Predict(AdversarialCritique)

    def forward(self, paper_text: str, lang_name: str):
        return self.critique(paper_text=paper_text, lang_name=lang_name)


class TranslationModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.translate = dspy.Predict(ContextAwareTranslation)

    def forward(self, paper_context: str, target_text: str, lang_name: str):
        return self.translate(
            paper_context=paper_context, target_text=target_text, lang_name=lang_name
        )


class VisionFigureModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(VisionAnalyzeFigure)

    def forward(self, caption_hint: str, lang_name: str):
        # Note: Image bytes handling is done at the LM level or prior to DSPy
        return self.analyze(caption_hint=caption_hint, lang_name=lang_name)


class ChatModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.chat = dspy.ChainOfThought(ChatGeneral)

    def forward(
        self,
        document_context: str,
        history_text: str,
        user_message: str,
        lang_name: str,
    ):
        return self.chat(
            document_context=document_context,
            history_text=history_text,
            user_message=user_message,
            lang_name=lang_name,
        )


class AuthorModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.chat = dspy.ChainOfThought(ChatAuthorPersona)

    def forward(self, paper_text: str, question: str, lang_name: str):
        return self.chat(paper_text=paper_text, question=question, lang_name=lang_name)


class ContextSummaryModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict(PaperSummaryContext)

    def forward(self, paper_text: str, max_length: int):
        return self.summarize(paper_text=paper_text, max_length=max_length)
