from concurrent.futures import ThreadPoolExecutor

from src.domain.features.tokenization import TokenizationService
from src.domain.features.word_analysis import WordAnalysisService
from src.domain.services.local_translator import LocalTranslatorService
from src.domain.services.nlp_service import NLPService

# 共通設定 (Legacy executor for backwards consistency if needed by external callers)
executor = ThreadPoolExecutor(max_workers=4)


class EnglishAnalysisService:
    """
    Facade for English analysis services.
    Delegates to specialized services and features.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EnglishAnalysisService, cls).__new__(cls)
            cls._instance._initialized_flag = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized_flag", False):
            return

        import os

        from src.domain.services.pdf_ocr_service import PDFOCRService

        self.nlp_service = NLPService()
        self.word_analysis = WordAnalysisService()
        self.tokenization = TokenizationService()
        self.local_translator = LocalTranslatorService()

        # Initialize OCR service
        self.model = os.getenv("MODEL_OCR", "gemini-2.0-flash-lite")
        self.ocr_service = PDFOCRService(self.model)

        # Maintain public properties if they were used outside
        self.translation_cache = self.word_analysis.translation_cache
        self._initialized_flag = True

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

    def translate_local(self, text: str, src_lang: str = "en", tgt_lang: str = "ja") -> str | None:
        """Translate text using local M2M100 model."""
        return self.local_translator.translate(text, src_lang=src_lang, tgt_lang=tgt_lang)

    # Legacy accessors
    def get_translation_cache(self):
        return self.word_analysis.translation_cache
