import dspy

from common.dspy_seed_prompt import (
    ADVERSARIAL_CRITIQUE_SEED,
    CHAT_GENERAL_SEED,
    CONTEXT_AWARE_TRANSLATION_SEED,
    PAPER_RECOMMENDATION_SEED,
    PAPER_SUMMARY_SECTIONS_SEED,
    PAPER_SUMMARY_SEED,
    PERSONA_ADAPTER_SEED,
    SENTENCE_TRANSLATION_SEED,
    SIMPLE_TRANSLATION_SEED,
    SYSTEM_CONTEXT_SEED,
    VISION_FIGURE_SEED,
    DEEP_EXPLANATION_SEED,
)

# =============================================================
# System Layer
# =============================================================


class SystemContextSignature(dspy.Signature):
    __doc__ = SYSTEM_CONTEXT_SEED

    task_type: str = dspy.InputField(
        desc="Type of task being performed (e.g. 'translation', 'summarization', 'critical review')."
    )
    lang_name: str = dspy.InputField(desc="Target output language.")

    system_context: str = dspy.OutputField(
        desc=(
            "Global role definition and invariant behavioral rules: "
            "assistant identity, language enforcement, output quality standards. "
            "Must not contain user-specific or content-specific information."
        )
    )


# =============================================================
# Persona Adapter
# =============================================================


class PersonaAdapterSignature(dspy.Signature):
    __doc__ = PERSONA_ADAPTER_SEED

    system_context: str = dspy.InputField(
        desc="Global role and invariant rules from the system layer. Persona instructions must not contradict these."
    )
    user_persona: str = dspy.InputField(
        desc="Description of the user's expertise, interests, and preferences."
    )
    task_description: str = dspy.InputField(
        desc="Brief description of the task type (e.g. 'translation', 'paper summary'). Not the content itself."
    )
    lang_name: str = dspy.InputField(desc="Target language name for the response.")

    persona_instruction: str = dspy.OutputField(
        desc=(
            "Behavioral policy for the assistant: how to adjust tone, "
            "terminology complexity, explanation depth, and language style. "
            "Must not contain task-specific content or contradict system_context."
        )
    )


# =============================================================
# Behavioral Analysis & Personalized Response Signatures
# =============================================================


class ExtractUserTraits(dspy.Signature):
    behavior_logs = dspy.InputField()

    interests = dspy.OutputField()
    expertise_level = dspy.OutputField()
    explanation_preference = dspy.OutputField()
    key_words = dspy.OutputField()
    stress_level = dspy.OutputField(desc="The user's stress level")


class BuildDecisionProfile(dspy.Signature):
    current_logs = dspy.InputField(desc="The user's current behavior logs")
    user_feedback = dspy.InputField(desc="The user's feedback")
    interests = dspy.InputField(desc="The user's interests")
    expertise_level = dspy.InputField(desc="The user's expertise level")
    explanation_preference = dspy.InputField(desc="The user's explanation preference")
    key_words = dspy.InputField(desc="The user's key words")
    stress_level = dspy.InputField(desc="The user's stress level")

    user_persona = dspy.OutputField(desc="The user's persona")


class SolveTask(dspy.Signature):
    """ユーザーペルソナと入力データからパーソナライズされたタスク指示を生成する"""

    user_persona = dspy.InputField(desc="The user's persona")
    lang_name = dspy.InputField(desc="The target language name")
    input_data = dspy.InputField(desc="The main input data for the task")
    task_instruction: str = dspy.OutputField(
        desc="Personalized task instruction optimized for the user's persona and language"
    )


# =============================================================
# Summary (要約系) の DSPy Signatures
# =============================================================


class PaperSummary(dspy.Signature):
    __doc__ = PAPER_SUMMARY_SEED

    input_data: str = dspy.InputField(desc="The full paper text or abstract")
    overview: str = dspy.OutputField(
        desc="Overview and high-level summary (1-2 sentences)"
    )
    key_contributions: list[str] = dspy.OutputField(
        desc="Main contributions and novel points (3-5 items)"
    )
    methodology: str = dspy.OutputField(
        desc="Concise explanation of research methodology"
    )
    conclusion: str = dspy.OutputField(desc="Conclusion and key findings")
    key_words: list[str] = dspy.OutputField(desc="Keywords (5-10 terms in English)")


class PaperSummarySections(dspy.Signature):
    __doc__ = PAPER_SUMMARY_SECTIONS_SEED

    input_data: str = dspy.InputField(desc="The full paper text or section content")
    sections: list[dict] = dspy.OutputField(
        desc="Section-by-section summary list [{'section': '...', 'summary': '...'}]"
    )


class PaperSummaryContext(dspy.Signature):
    """Generate a brief summary of the paper for AI context."""

    input_data = dspy.InputField(desc="Segment of the paper text")
    max_length = dspy.InputField(desc="Maximum number of characters for the summary")
    summary = dspy.OutputField(desc="Brief summary text")


# =============================================================
# Chat (対話系) の DSPy Signatures
# =============================================================


class ChatGeneral(dspy.Signature):
    __doc__ = CHAT_GENERAL_SEED

    input_data: str = dspy.InputField(desc="The user's current question or message")
    document_context: str = dspy.InputField(
        desc="Contextual information from the paper"
    )
    history_text: str = dspy.InputField(desc="Previous conversation history")
    answer: str = dspy.OutputField(desc="Text of the answer to the question")


# =============================================================
# Agent (分析・レビュー系) の DSPy Signatures
# =============================================================


class AdversarialCritique(dspy.Signature):
    __doc__ = ADVERSARIAL_CRITIQUE_SEED

    input_data: str = dspy.InputField(desc="The paper text to critique")
    hidden_assumptions: list[dict] = dspy.OutputField(
        desc="Hidden assumptions and their risks [{'assumption': '...', 'risk': '...', 'severity': '...'}]"
    )
    unverified_conditions: list[dict] = dspy.OutputField(
        desc="Unverified conditions and their impacts [{'condition': '...', 'impact': '...', 'severity': '...'}]"
    )
    reproducibility_risks: list[dict] = dspy.OutputField(
        desc="Risks related to reproducibility [{'risk': '...', 'detail': '...', 'severity': '...'}]"
    )
    methodology_concerns: list[dict] = dspy.OutputField(
        desc="Methodological concerns and suggestions [{'concern': '...', 'suggestion': '...', 'severity': '...'}]"
    )
    overall_assessment: str = dspy.OutputField(
        desc="Summary of the overall critical assessment"
    )


# =============================================================
# Vision (図表分析系) の DSPy Signatures
# =============================================================


class VisionAnalyzeFigure(dspy.Signature):
    __doc__ = VISION_FIGURE_SEED

    input_data: str = dspy.InputField(desc="Caption or textual hint about the figure")
    type_overview: str = dspy.OutputField(desc="Overview and type of the figure")
    key_findings: list[str] = dspy.OutputField(desc="Main trends or patterns")
    interpretation: str = dspy.OutputField(desc="Interpretation of data or trends")
    implications: str = dspy.OutputField(desc="Support for the paper's claims")
    highlights: list[str] = dspy.OutputField(desc="Notable points or anomalies")


# =============================================================
# 推薦機能 (Recommendation) の DSPy Signatures
# =============================================================


class PaperRecommendation(dspy.Signature):
    __doc__ = PAPER_RECOMMENDATION_SEED

    input_data: str = dspy.InputField(
        desc="Analysis of the current paper and user profile"
    )
    recommendations: list[str] = dspy.OutputField(
        desc="List of recommended papers (including titles and reasons)"
    )
    search_queries: list[str] = dspy.OutputField(
        desc="Search queries for Semantic Scholar"
    )


# =============================================================
# Translation (翻訳系) の DSPy Signatures
# =============================================================


class ContextAwareTranslation(dspy.Signature):
    __doc__ = CONTEXT_AWARE_TRANSLATION_SEED

    input_data: str = dspy.InputField(desc="The target word or phrase to translate")
    paper_context: str = dspy.InputField(
        desc="Academic paper context including surrounding sentences around the target word (paper summary and/or nearby text excerpt)"
    )
    translation_and_explanation: str = dspy.OutputField(
        desc="Concise translation based on context"
    )


class SimpleTranslation(dspy.Signature):
    __doc__ = SIMPLE_TRANSLATION_SEED

    input_data: str = dspy.InputField(desc="The word or phrase to translate")
    paper_context: str = dspy.InputField(desc="Academic context or summary")
    translation: str = dspy.OutputField(desc="Concise translation")


class SentenceTranslation(dspy.Signature):
    __doc__ = SENTENCE_TRANSLATION_SEED

    input_data: str = dspy.InputField(desc="The sentence to translate")
    paper_context: str = dspy.InputField(desc="Academic paper context")
    translation: str = dspy.OutputField(desc="Full translation of the sentence")


class DeepExplanation(dspy.Signature):
    __doc__ = DEEP_EXPLANATION_SEED

    input_data: str = dspy.InputField(desc="The target word or phrase to explain")
    summary_context: str = dspy.InputField(desc="Paper summary context")
    context: str = dspy.InputField(desc="Immediate surrounding text context")

    explanation: str = dspy.OutputField(desc="Detailed technical explanation")
