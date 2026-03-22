import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import OptionalUser
from app.core.config import is_production
from app.crud import get_storage_provider
from app.domain.features.figure_insight import FigureInsightService
from common import settings
from common.logger import ServiceLogger

log = ServiceLogger("Figures")


router = APIRouter(tags=["Figures"])
figure_service = FigureInsightService()


class ExplainRequest(BaseModel):
    """AI解析リクエスト。DBに存在しないトランジェントfigureの場合は image_url を渡す。"""

    image_url: str | None = None


@router.get("/papers/{paper_id}/figures")
async def get_paper_figures(paper_id: str, user: OptionalUser = None):
    """Get all figures for a paper."""
    try:
        storage = get_storage_provider()
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
    """image_url から画像バイトを取得する。

    ストレージ層 (Local/GCS) に委譲することで、Cloudflare Workers 等の
    認証済みエンドポイントへの HTTP リクエストを回避する。
    /static/... 相対パスおよびフロントエンドが API_URL を付与したフルURLの両方に対応。
    """
    import anyio
    from app.providers.image_storage import get_image_bytes

    try:
        if image_url.startswith("/static/") or image_url.startswith("http"):
            return await anyio.to_thread.run_sync(get_image_bytes, image_url)
    except Exception as e:
        log.warning(
            "fetch_image_bytes",
            "Storage fetch failed, falling back to HTTP",
            image_url=image_url,
            error=str(e),
        )

    # ストレージ層で処理できない URL: 直接 HTTP フェッチ
    if image_url.startswith("http"):
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
        storage = get_storage_provider()
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

        # GCS 環境かつ Vertex AI プロバイダーの場合のみ URI を直接渡す（Gemini API は gs:// 非対応）

        import anyio
        from app.providers.image_storage import resolve_gcs_uri

        gcs_result = await anyio.to_thread.run_sync(resolve_gcs_uri, image_url)
        use_vertex = str(settings.get("AI_PROVIDER", "vertex")).lower() == "vertex"
        if gcs_result and use_vertex:
            gcs_uri, mime_type = gcs_result
            log.debug(
                "explain_figure",
                "Using GCS URI directly (no download)",
                figure_id=figure_id,
                gcs_uri=gcs_uri,
                mime_type=mime_type,
            )
            explanation = await figure_service.analyze_figure(
                image_uri=gcs_uri, caption=caption, target_lang="ja", mime_type=mime_type
            )
        else:
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
                image_bytes=image_bytes, caption=caption, target_lang="ja", mime_type="image/jpeg"
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
