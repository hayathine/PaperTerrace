from concurrent.futures import ThreadPoolExecutor

# 共通設定 (Legacy executor for backwards consistency if needed by external callers)
executor = ThreadPoolExecutor(max_workers=4)


class EnglishAnalysisService:
    """
    Facade for English analysis services.
    Delegates to specialized services and features.
    """

    def __init__(self):
        import os

        from app.domain.features.tokenization import TokenizationService
        from app.domain.features.word_analysis import WordAnalysisService
        from app.domain.services.pdf_ocr_service import PDFOCRService

        self.word_analysis = WordAnalysisService()
        self.tokenization = TokenizationService()

        # Initialize OCR service
        self.model = os.getenv("MODEL_OCR", "gemini-2.5-flash-lite")
        self.ocr_service = PDFOCRService(self.model)

        # Maintain public properties if they were used outside
        self.word_cache = self.word_analysis.word_cache
        self.translation_cache = self.word_analysis.translation_cache

    async def tokenize_stream(self, text, paper_id=None, lang="ja", session_id=None):
        """Processes text paragraph by paragraph and yields interactive HTML."""
        async for chunk in self.tokenization.tokenize_stream(
            text, paper_id=paper_id, lang=lang, session_id=session_id
        ):
            yield chunk

    async def get_translation(
        self,
        lemma: str,
        context: str | None = None,
        lang: str = "ja",
        session_id: str | None = None,
    ):
        """Get translation for a lemma, optionally using context."""
        return await self.word_analysis.translate(
            lemma, lang=lang, context=context, session_id=session_id
        )

    # Legacy accessors
    def get_word_cache(self):
        return self.word_analysis.word_cache

    def get_translation_cache(self):
        return self.word_analysis.translation_cache
