from app.domain.features.figure_insight import FigureInsightService
from app.domain.features.summary import SummaryService
from app.providers import get_storage_provider
from common.logger import ServiceLogger

log = ServiceLogger("Processing")
# FigureInsightService は DB セッションを持たないためシングルトンで問題なし。
# storage はモジュールレベルで生成すると SessionLocal() がプロセス終了まで
# コネクションを占有し続けるため、各タスク内で都度生成・クローズする。
figure_insight = FigureInsightService()


async def process_figure_analysis_task(
    figure_id: str,
    image_url: str,
    lang: str = "ja",
    user_id: str | None = None,
    session_id: str | None = None,
):
    """
    Background task to analyze figure.
    """
    if not figure_id:
        return

    log.info("figure_task", "Analysis task started", figure_id=figure_id)

    storage = get_storage_provider()
    try:
        figure = storage.get_figure(figure_id)
        if not figure:
            log.warning("figure_task", "Figure not found in DB", figure_id=figure_id)
            return

        # Skip if already has explanation
        if figure.get("explanation"):
            log.info(
                "figure_task",
                "Figure already has explanation, skipping.",
                figure_id=figure_id,
            )
            return

        import anyio
        from app.providers.image_storage import get_gcs_uri, get_image_bytes

        # GCS URI が取得できる場合はバイトダウンロードを省略
        gcs_uri = await anyio.to_thread.run_sync(get_gcs_uri, image_url)
        if gcs_uri:
            explanation = await figure_insight.analyze_figure(
                image_uri=gcs_uri,
                caption=figure.get("caption", ""),
                mime_type="image/jpeg",
                target_lang=lang,
                user_id=user_id,
                session_id=session_id,
                paper_id=figure.get("paper_id"),
            )
        else:
            # ローカル環境: ストレージ層から直接取得（HTTP経由ではなく）
            try:
                image_bytes = await anyio.to_thread.run_sync(get_image_bytes, image_url)
            except Exception:
                log.warning(
                    "figure_task", "Could not retrieve image bytes", image_url=image_url
                )
                return

            explanation = await figure_insight.analyze_figure(
                image_bytes,
                caption=figure.get("caption", ""),
                mime_type="image/jpeg",
                target_lang=lang,
                user_id=user_id,
                session_id=session_id,
                paper_id=figure.get("paper_id"),
            )
        storage.update_figure_explanation(figure_id, explanation)

        label = figure.get("label", "figure")
        log.info(
            "figure_task", "SUCCESS: updated analysis", label=label, figure_id=figure_id
        )

    except Exception as e:
        log.error(
            "figure_task",
            "Analysis FAILED",
            figure_id=figure_id,
            error=str(e),
            exc_info=True,
        )
    finally:
        storage.close()


async def process_paper_summary_task(
    paper_id: str,
    lang: str = "ja",
    user_id: str | None = None,
    session_id: str | None = None,
):
    """
    Background task to summarize paper.
    """
    if not paper_id:
        return

    log.info("summary_task", "Summary task started", paper_id=paper_id)

    storage = get_storage_provider()
    try:
        paper = storage.get_paper(paper_id)
        if not paper or not paper.get("ocr_text"):
            log.warning(
                "summary_task", "Paper or its text not found", paper_id=paper_id
            )
            return

        # Skip if already has summary
        if paper.get("full_summary"):
            log.info(
                "summary_task",
                "Paper already has full summary, skipping.",
                paper_id=paper_id,
            )
            return

        # Execute summary
        summary_service = SummaryService(storage=storage)
        await summary_service.summarize_full(
            text=paper["ocr_text"],
            target_lang=lang,
            paper_id=paper_id,
            user_id=user_id,
            session_id=session_id,
        )
        log.info(
            "summary_task", "SUCCESS: generated summary for paper", paper_id=paper_id
        )

    except Exception as e:
        log.error(
            "summary_task",
            "Summary FAILED",
            paper_id=paper_id,
            error=str(e),
            exc_info=True,
        )
    finally:
        storage.close()
