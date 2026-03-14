import dspy

from common.dspy.signatures import (
    AdversarialCritique,
    BuildDecisionProfile,
    ChatGeneral,
    ContextAwareTranslation,
    DeepExplanation,
    ExtractUserTraits,
    PaperRecommendation,
    PaperSummary,
    PaperSummaryContext,
    PaperSummarySections,
    SimpleTranslation,
    SolveTask,
    VisionAnalyzeFigure,
)


class UserPersonaModule(dspy.Module):
    """ユーザーの行動ログから特性を抽出し、推論方針（ペルソナ）を構築する2段階のモジュール"""

    def __init__(self):
        super().__init__()
        self.extract_traits = dspy.Predict(ExtractUserTraits)
        self.build_persona = dspy.Predict(BuildDecisionProfile)

    def forward(self, behavior_logs: str, current_logs: str, user_feedback: str):
        # 1. 行動ログから特性（興味、専門性、好みなど）を抽出
        traits = self.extract_traits(behavior_logs=behavior_logs)

        # 2. 抽出された特性と現在の状況を組み合わせて推論用ペルソナを構築
        result = self.build_persona(
            current_logs=current_logs,
            user_feedback=user_feedback,
            interests=traits.interests,
            expertise_level=traits.expertise_level,
            explanation_preference=traits.explanation_preference,
            key_words=traits.key_words,
            stress_level=traits.stress_level,
        )
        return result


class UniversalTaskModule(dspy.Module):
    """
    SolveTask（パーソナライズ）と任意の下流タスクシグネチャを動的に結合して実行する汎用モジュール。
    """

    def __init__(self, signature=SolveTask, skip_optimizers=False):
        super().__init__()
        self.signature = signature
        self.solve = dspy.Predict(signature)  # GEPA最適化対象

    def forward(self, **kwargs):
        return self.solve(**kwargs)


# --- 以下、UniversalTaskModule のラッパーとして各モジュールを定義 ---


class RecommendationModule(UniversalTaskModule):
    """論文の解析結果とユーザープロフィールを照らし合わせ、パーソナライズされた推薦を行うモジュール"""

    def __init__(self):
        super().__init__(PaperRecommendation, skip_optimizers=False)

    def forward(self, paper_analysis: str, **kwargs):
        result = super().forward(
            input_data=paper_analysis,
            task_instruction="Provide personalized paper recommendations based on the user's persona.",
            **kwargs,
        )

        # 推薦固有の制約
        dspy.Assert(len(result.recommendations) >= 3, "推薦は3件以上必要")
        dspy.Assert(len(result.search_queries) >= 2, "検索クエリは2件以上必要")

        # user_persona または kwargs から情報を取得して Suggest を行う
        user_persona = kwargs.get("user_persona", "")
        persona_lower = user_persona.lower()
        dspy.Suggest(
            not ("初級" in user_persona or "beginner" in persona_lower)
            or any("survey" in r.lower() for r in result.recommendations),
            "初級ユーザーにはsurvey論文を含めることを推奨",
        )

        return result


class PaperSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummary)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            task_instruction="Generate a comprehensive summary of the paper based on the provided text.",
            **kwargs,
        )


class SectionSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummarySections)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            task_instruction="Provide section-by-section summaries for the provided paper text.",
            **kwargs,
        )


class ContextSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummaryContext)

    def forward(self, paper_text: str, max_length: int = 500, **kwargs):
        return super().forward(
            input_data=paper_text,
            max_length=max_length,
            task_instruction="Provide a brief summary for AI context.",
            **kwargs,
        )


class AdversarialModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(AdversarialCritique)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            task_instruction="Critically analyze the paper and identify hidden assumptions and potential risks.",
            **kwargs,
        )


class TranslationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(ContextAwareTranslation)

    def forward(self, paper_context: str, target_word: str, **kwargs):
        return super().forward(
            paper_context=paper_context,
            input_data=target_word,
            task_instruction="Translate the target text considering the academic context.",
            **kwargs,
        )


class SimpleTranslationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(SimpleTranslation)

    def forward(self, paper_context: str, target_word: str, **kwargs):
        return super().forward(
            paper_context=paper_context,
            input_data=target_word,
            task_instruction="Provide a concise translation for the target word.",
            **kwargs,
        )


class DeepExplanationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(DeepExplanation)

    def forward(self, summary_context: str, context: str, target_word: str, **kwargs):
        return super().forward(
            summary_context=summary_context,
            context=context,
            input_data=target_word,
            task_instruction="Provide a deep, context-aware explanation for the target word.",
            **kwargs,
        )


class VisionFigureModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(VisionAnalyzeFigure)

    def forward(self, caption_hint: str, **kwargs):
        return super().forward(
            input_data=caption_hint,
            task_instruction="Analyze the provided figure or table based on its context and caption.",
            **kwargs,
        )


class ChatModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(ChatGeneral)

    def forward(
        self, document_context: str, history_text: str, user_message: str, **kwargs
    ):
        return super().forward(
            document_context=document_context,
            history_text=history_text,
            user_message=user_message,
            input_data=user_message,
            task_instruction="Answer the user's question about the academic paper.",
            **kwargs,
        )
