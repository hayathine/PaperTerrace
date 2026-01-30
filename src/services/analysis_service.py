from concurrent.futures import ThreadPoolExecutor

from src.features.tokenization import TokenizationService
from src.features.word_analysis import WordAnalysisService
from src.services.nlp_service import NLPService

# 共通設定 (Legacy executor for backwards consistency if needed by external callers)
executor = ThreadPoolExecutor(max_workers=4)


class EnglishAnalysisService:
    """
    Facade for English analysis services.
    Delegates to specialized services and features.
    """

    def __init__(self):
        import os

        from src.services.pdf_ocr_service import PDFOCRService

        self.nlp_service = NLPService()
        self.word_analysis = WordAnalysisService()
        self.tokenization = TokenizationService()

        # Initialize OCR service
        self.model = os.getenv("MODEL_OCR", "gemini-2.5-flash-lite")
        self.ocr_service = PDFOCRService(self.model)

        # Maintain public properties if they were used outside
        self.word_cache = self.word_analysis.word_cache
        self.translation_cache = self.word_analysis.translation_cache

    def lemmatize(self, text: str) -> str:
        """Get lemma for text using NLP service."""
        return self.nlp_service.lemmatize(text)

    async def tokenize_stream(self, *args, **kwargs):
        """Processes text paragraph by paragraph and yields interactive HTML."""
        async for chunk in self.tokenization.tokenize_stream(*args, **kwargs):
            yield chunk

    async def get_translation(self, lemma: str, context: str | None = None, lang: str = "ja"):
        """Get translation for a lemma, optionally using context."""
        return await self.word_analysis.lookup_or_translate(lemma, lang=lang, context=context)

    # Legacy accessors
    def get_word_cache(self):
        return self.word_analysis.word_cache

    def get_translation_cache(self):
        return self.word_analysis.translation_cache
