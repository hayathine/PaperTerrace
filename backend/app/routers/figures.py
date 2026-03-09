import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import OptionalUser
from app.core.config import is_production
from app.crud import get_storage_provider
from app.domain.features.figure_insight import FigureInsightService
from common.logger import ServiceLogger

log = ServiceLogger("Figures")


router = APIRouter(tags=["Figures"])
storage = get_storage_provider()
figure_service = FigureInsightService()


class ExplainRequest(BaseModel):
    """AI解析リクエスト。DBに存在しないトランジェントfigureの場合は image_url を渡す。"""

    image_url: str | None = None


@router.get("/papers/{paper_id}/figures")
async def get_paper_figures(paper_id: str, user: OptionalUser = None):
    """Get all figures for a paper."""
    try:
        figures = storage.get_paper_figures(paper_id)
        return {"figures": figures}
    except Exception as e:
        log.error(
            "get_figures", "Failed to get figures", error=str(e), paper_id=paper_id
        )

        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while fetching figures."
        )
        return JSONResponse({"error": error_msg}, status_code=500)


async def _fetch_image_bytes(image_url: str) -> bytes | None:
    """image_url から画像バイトを取得する。ローカルパスと HTTP URL の両方に対応。"""
    if image_url.startswith("/static/"):
        relative_path = image_url.lstrip("/")
        file_path = f"src/{relative_path}"
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
    elif image_url.startswith("http"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            if resp.status_code == 200:
                return resp.content
    return None


@router.post("/figures/{figure_id}/explain")
async def explain_figure(
    figure_id: str,
    body: ExplainRequest = ExplainRequest(),
    user: OptionalUser = None,
):
    """Generate or retrieve explanation for a figure.

    登録ユーザーのfigureはDBから取得する。未登録ユーザーのトランジェントfigureは
    DBに存在しないため、リクエストボディの image_url を使って直接解析する。
    """
    try:
        figure = storage.get_figure(figure_id)

        if figure:
            # DB登録済み: キャッシュ済み解説があればそのまま返す
            if figure.get("explanation"):
                return {"explanation": figure["explanation"]}
            image_url = figure.get("image_url")
            caption = figure.get("caption", "")
        elif body.image_url:
            # トランジェントfigure: DBにないがimage_urlで直接解析する
            log.info(
                "explain_figure",
                "Transient figure: explaining from image_url",
                figure_id=figure_id,
            )
            image_url = body.image_url
            caption = ""
        else:
            log.warning(
                "explain_figure",
                "Figure not found in DB and no image_url provided",
                figure_id=figure_id,
            )
            raise HTTPException(status_code=404, detail="Figure not found")

        if not image_url:
            log.warning(
                "explain_figure",
                "No image URL available",
                figure_id=figure_id,
            )
            raise HTTPException(status_code=400, detail="No image URL")

        image_bytes = await _fetch_image_bytes(image_url)
        if not image_bytes:
            log.warning(
                "explain_figure",
                "Image file not found",
                figure_id=figure_id,
                image_url=image_url,
            )
            raise HTTPException(status_code=404, detail="Image file not found")

        explanation = await figure_service.analyze_figure(
            image_bytes, caption=caption, target_lang="ja"
        )

        # DB登録済みfigureのみ解説をキャッシュする
        if figure:
            storage.update_figure_explanation(figure_id, explanation)

        return {"explanation": explanation}

    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "explain_figure",
            "Failed to explain figure",
            error=str(e),
            figure_id=figure_id,
        )

        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while explaining the figure."
        )
        return JSONResponse({"error": error_msg}, status_code=500)
