from app.domain.services.analysis_service import EnglishAnalysisService, executor
from app.domain.services.nlp_service import nlp
from app.domain.services.pdf_ocr_service import PDFOCRService

# Re-export definitions to maintain compatibility with existing imports
__all__ = [
    "PDFOCRService",
    "EnglishAnalysisService",
    "executor",
    "nlp",
]
