from src.services.analysis_service import EnglishAnalysisService, executor, nlp
from src.services.pdf_ocr_service import PDFOCRService

# Re-export definitions to maintain compatibility with existing imports
__all__ = [
    "PDFOCRService",
    "EnglishAnalysisService",
    "executor",
    "nlp",
]
