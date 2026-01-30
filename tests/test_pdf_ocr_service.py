import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock google.cloud.vision dependency since it might be missing in the environment
# and we don't want tests to fail on import.
mock_vision_module = MagicMock()
sys.modules["google.cloud.vision"] = mock_vision_module

# Also ensure "from google.cloud import vision" works
try:
    import google.cloud
except ImportError:
    google = MagicMock()
    sys.modules["google"] = google
    sys.modules["google.cloud"] = MagicMock()

if "google.cloud" in sys.modules:
    sys.modules["google.cloud"].vision = mock_vision_module
else:
    # Fallback if imports are weird
    mock_cloud = MagicMock()
    mock_cloud.vision = mock_vision_module
    sys.modules["google.cloud"] = mock_cloud

# Ensure the module is loaded so it can be patched
import src.providers.vision_ocr  # noqa: E402
from src.services.pdf_ocr_service import PDFOCRService  # noqa: E402


@pytest.fixture
def mock_dependencies():
    with (
        patch("src.services.pdf_ocr_service.get_ai_provider") as mock_ai,
        patch("src.services.pdf_ocr_service.FigureService") as mock_figure_cls,
        patch("src.services.pdf_ocr_service.LanguageService") as mock_lang_cls,
        patch("src.services.pdf_ocr_service.get_ocr_from_db") as mock_get_db,
        patch("src.services.pdf_ocr_service.save_ocr_to_db") as mock_save_db,
        patch("src.services.pdf_ocr_service.get_page_images") as mock_get_imgs,
        patch("src.services.pdf_ocr_service.save_page_image") as mock_save_img,
        patch("pypdf.PdfReader") as mock_pdf_reader,
    ):
        mock_pdf_reader.return_value.pages = []
        yield {
            "ai": mock_ai,
            "figure_cls": mock_figure_cls,
            "lang_cls": mock_lang_cls,
            "get_db": mock_get_db,
            "save_db": mock_save_db,
            "get_imgs": mock_get_imgs,
            "save_img": mock_save_img,
            "pdf_reader": mock_pdf_reader,
        }


@pytest.fixture
def ocr_service(mock_dependencies):
    service = PDFOCRService(model="test-model")
    # Mock initialized services
    service.figure_service = MagicMock()
    service.figure_service.detect_and_extract_figures = AsyncMock(return_value=[])
    service.language_service = MagicMock()
    return service


@pytest.mark.asyncio
async def test_detect_language_from_pdf(ocr_service):
    """Test language detection delegation."""
    ocr_service.language_service.detect_language = AsyncMock(return_value="ja")
    lang = await ocr_service.detect_language_from_pdf(b"pdf_bytes")
    assert lang == "ja"
    ocr_service.language_service.detect_language.assert_called_once_with(b"pdf_bytes")


@pytest.mark.asyncio
async def test_extract_text_streaming_cache_hit(ocr_service, mock_dependencies):
    """Test extracting text when cache exists."""
    # Setup cache hit
    mock_dependencies["get_db"].return_value = {"ocr_text": "Cached Text", "layout_json": None}
    mock_dependencies["get_imgs"].return_value = ["img1.png", "img2.png"]

    results = []
    async for page in ocr_service.extract_text_streaming(b"pdf_bytes", "test.pdf"):
        results.append(page)

    assert len(results) == 2
    # Check assertions based on _handle_cache implementation
    # Pages are 1-indexed in return
    assert results[0][0] == 1  # page_num
    assert results[0][2] == "Cached Text"  # First page has text
    assert results[0][5] == "img1.png"  # Image URL

    assert results[1][0] == 2
    assert results[1][2] == ""  # Subsequent pages empty text
    assert results[1][5] == "img2.png"


@pytest.mark.asyncio
async def test_extract_text_streaming_cache_miss(ocr_service, mock_dependencies):
    """Test extracting text when cache misses (doing actual OCR)."""
    # Setup cache miss
    mock_dependencies["get_db"].return_value = None

    # Mock pdfplumber
    with patch("src.services.pdf_ocr_service.pdfplumber.open") as mock_pdfplumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.page_number = 1

        # Mock extract_words return value: list of dicts with word, x0, top, x1, bottom
        mock_page.extract_words.return_value = [
            {"text": "Hello", "x0": 0, "top": 0, "x1": 10, "bottom": 10},
            {"text": "World", "x0": 20, "top": 0, "x1": 30, "bottom": 10},
        ]

        # Mock to_image
        mock_img_obj = MagicMock()
        mock_pil_image = MagicMock()
        mock_pil_image.width = 100
        mock_pil_image.height = 100
        mock_pil_image.convert.return_value = mock_pil_image
        mock_img_obj.original = mock_pil_image
        mock_page.to_image.return_value = mock_img_obj

        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        results = []
        async for page in ocr_service.extract_text_streaming(b"pdf_bytes", "test.pdf"):
            results.append(page)

        assert len(results) == 1
        page_num, total, text, is_last, hash, url, layout = results[0]

        assert page_num == 1
        assert total == 1
        assert text == "Hello World"
        assert is_last is True
        assert layout is not None
        assert layout["width"] == 100

        # Verify save to DB and Image was called
        mock_dependencies["save_db"].assert_called_once()
        mock_dependencies["save_img"].assert_called_once()


@pytest.mark.asyncio
async def test_extract_text_streaming_ocr_fallback(ocr_service, mock_dependencies):
    """Test fallback to Vision API when native text extraction fails."""
    mock_dependencies["get_db"].return_value = None

    with (
        patch("src.services.pdf_ocr_service.pdfplumber.open") as mock_pdfplumber,
        # Patch the class directly on the imported module to avoid path resolution issues
        patch.object(src.providers.vision_ocr, "VisionOCRService") as MockVisionService,
    ):
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.page_number = 1

        # Native extraction returns empty
        mock_page.extract_words.return_value = []
        mock_page.extract_text.return_value = ""

        # Image
        mock_img_obj = MagicMock()
        mock_pil_image = MagicMock()
        mock_pil_image.width = 100
        mock_pil_image.height = 100
        mock_pil_image.convert.return_value = mock_pil_image
        mock_img_obj.original = mock_pil_image
        mock_page.to_image.return_value = mock_img_obj

        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf

        # Setup Vision Service Mock
        mock_vision_instance = MockVisionService.return_value
        mock_vision_instance.is_available.return_value = True
        mock_vision_instance.detect_text_with_layout = AsyncMock(
            return_value=("Vision Text", {"words": []})
        )

        results = []
        async for page in ocr_service.extract_text_streaming(b"pdf_bytes", "test.pdf"):
            results.append(page)

        assert len(results) == 1
        assert results[0][2] == "Vision Text"
