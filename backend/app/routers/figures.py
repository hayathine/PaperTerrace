from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.auth import OptionalUser
from app.crud import get_storage_provider
from app.domain.features.figure_insight import FigureInsightService
from app.logger import logger

router = APIRouter(tags=["Figures"])
storage = get_storage_provider()
figure_service = FigureInsightService()


@router.get("/api/papers/{paper_id}/figures")
async def get_paper_figures(paper_id: str, user: OptionalUser = None):
    """Get all figures for a paper."""
    try:
        figures = storage.get_paper_figures(paper_id)
        return {"figures": figures}
    except Exception as e:
        logger.error(f"Failed to get figures: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/figures/{figure_id}/explain")
async def explain_figure(figure_id: str, user: OptionalUser = None):
    """Generate or retrieve explanation for a figure."""
    try:
        figure = storage.get_figure(figure_id)
        if not figure:
            raise HTTPException(status_code=404, detail="Figure not found")

        if figure.get("explanation"):
            return {"explanation": figure["explanation"]}

        # Generate explanation
        image_url = figure.get("image_url")
        if not image_url:
            raise HTTPException(status_code=400, detail="No image URL")

        # We need the image bytes.
        # Image URL is like /static/paper_images/...
        # We need to map it back to specific storage or fetch it.
        # This is a bit tricky if using GCS vs Local.

        # HACK: Assume Local for now or use the path to read.
        # Ideally ImageStorage should have `read(path)` or similar.
        # But we only have `get_list`.

        # Let's try to reverse the URL to file path for local.
        # url: /static/paper_images/{hash}/{filename}
        # local: src/static/paper_images/{hash}/{filename}

        image_bytes = None

        import os

        if image_url.startswith("/static/"):
            # Local file
            relative_path = image_url.lstrip("/")  # static/paper_images/...
            file_path = f"src/{relative_path}"
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
        elif image_url.startswith("http"):
            # GCS signed URL or similar
            # Fetch it
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url)
                if resp.status_code == 200:
                    image_bytes = resp.content

        if not image_bytes:
            raise HTTPException(status_code=404, detail="Image file not found")

        explanation = await figure_service.analyze_figure(
            image_bytes, caption=figure.get("caption", ""), target_lang="ja"
        )

        # Save it
        storage.update_figure_explanation(figure_id, explanation)

        return {"explanation": explanation}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to explain figure: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
