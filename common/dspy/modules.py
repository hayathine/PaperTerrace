import dspy

from common.dspy.signatures import (
    AdversarialCritique,
    ChatGeneral,
    ContextAwareTranslation,
    PaperSummary,
    PaperSummaryContext,
    PaperSummarySections,
    VisionAnalyzeFigure,
)


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


class ContextSummaryModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict(PaperSummaryContext)

    def forward(self, paper_text: str, max_length: int):
        return self.summarize(paper_text=paper_text, max_length=max_length)
