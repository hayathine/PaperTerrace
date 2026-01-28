import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# fitz (PyMuPDF) specific mocking needs care due to C-extension nature
# We mock it before importing the target module if possible, or patch where used.
from src.logic import PDFOCRService


class TestPDFOCRServiceLanguageDetection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_provider_patcher = patch("src.logic.get_ai_provider")
        self.mock_get_provider = self.mock_provider_patcher.start()
        self.mock_provider = AsyncMock()
        self.mock_get_provider.return_value = self.mock_provider

        # Create service instance (OCR model can be dummy)
        self.service = PDFOCRService(model="dummy-model")

    async def asyncTearDown(self):
        self.mock_provider_patcher.stop()

    async def test_detect_language_from_metadata(self):
        """Should detect language from PDF metadata if present."""

        # Mock fitz module in sys.modules
        mock_fitz = MagicMock()
        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            # Setup mock doc
            mock_doc = MagicMock()
            mock_fitz.open.return_value = mock_doc

            # Mock pdf_catalog and xref_get_key
            mock_doc.pdf_catalog.return_value = 123
            # Return valid lang entry: (type, value)
            mock_doc.xref_get_key.return_value = ("string", "ja-JP")

            lang = await self.service.detect_language_from_pdf(b"dummy_bytes")

            self.assertEqual(lang, "ja")
            mock_doc.close.assert_called()

    async def test_detect_language_fallback_to_ai(self):
        """Should fallback to AI detection if metadata is missing."""
        mock_fitz = MagicMock()
        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            mock_doc = MagicMock()
            mock_fitz.open.return_value = mock_doc
            mock_doc.__len__.return_value = 1

            # Metadata missing
            mock_doc.xref_get_key.return_value = ("null", None)

            # Page extraction
            mock_page = MagicMock()
            mock_page.get_text.return_value = "This is an English text sample."
            mock_doc.__getitem__.return_value = mock_page

            # AI response
            self.mock_provider.generate.return_value = "en"

            lang = await self.service.detect_language_from_pdf(b"dummy_bytes")

            self.assertEqual(lang, "en")

            # Verify AI was called
            self.mock_provider.generate.assert_called()
            args, _ = self.mock_provider.generate.call_args
            self.assertIn("This is an English text sample.", args[0])


if __name__ == "__main__":
    unittest.main()
