from app.domain.features.figure_insight import FigureInsightService
from app.domain.features.summary import SummaryService
from app.domain.services.grobid_service import GROBIDService
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
        from app.providers.image_storage import get_image_bytes, resolve_gcs_uri

        # GCS URI が取得できる場合はバイトダウンロードを省略
        gcs_result = await anyio.to_thread.run_sync(resolve_gcs_uri, image_url)
        if gcs_result:
            gcs_uri, mime_type = gcs_result
            explanation = await figure_insight.analyze_figure(
                image_uri=gcs_uri,
                caption=figure.get("caption", ""),
                mime_type=mime_type,
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
            storage.update_processing_status(paper_id, "summary_status", "skipped")
            return

        # Skip if already has summary
        if paper.get("full_summary"):
            log.info(
                "summary_task",
                "Paper already has full summary, skipping.",
                paper_id=paper_id,
            )
            storage.update_processing_status(paper_id, "summary_status", "success")
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
        storage.update_processing_status(paper_id, "summary_status", "success")
        log.info(
            "summary_task", "SUCCESS: generated summary for paper", paper_id=paper_id
        )

    except Exception as e:
        storage.update_processing_status(paper_id, "summary_status", "failed")
        log.error(
            "summary_task",
            "Summary FAILED",
            paper_id=paper_id,
            error=str(e),
            exc_info=True,
        )
    finally:
        storage.close()


async def process_grobid_enrichment_task(paper_id: str, file_hash: str) -> None:
    """
    GROBID で論文構造解析を行い DB を更新するバックグラウンドタスク。

    title / authors / abstract / ocr_text（構造化 Markdown）を更新する。
    GROBID が無効・失敗した場合は静かに終了する。
    """
    if not paper_id or not file_hash:
        return

    grobid = GROBIDService()
    if not grobid.is_available():
        log.info("grobid_task", "GROBID 無効のためスキップ", paper_id=paper_id)
        storage = get_storage_provider()
        try:
            storage.update_processing_status(paper_id, "grobid_status", "skipped")
        finally:
            storage.close()
        return

    log.info("grobid_task", "GROBID エンリッチメント開始", paper_id=paper_id)

    storage = get_storage_provider()
    try:
        paper = storage.get_paper(paper_id)
        if not paper:
            log.warning("grobid_task", "Paper が見つからない", paper_id=paper_id)
            return

        # 既に GROBID テキストが存在する場合はスキップしてステータスを修復するだけ
        if paper.get("grobid_text"):
            log.info("grobid_task", "GROBID テキスト既存のためスキップ", paper_id=paper_id)
            storage.update_processing_status(paper_id, "grobid_status", "success")
            return

        from app.providers.image_storage import get_image_storage  # noqa: PLC0415

        img_storage = get_image_storage()
        pdf_bytes = img_storage.get_doc_bytes(img_storage.get_doc_path(file_hash))

        result = await grobid.process_fulltext_document(pdf_bytes)
        if not result:
            log.warning("grobid_task", "GROBID 解析失敗", paper_id=paper_id)
            storage.update_processing_status(paper_id, "grobid_status", "failed")
            return

        # GROBID がセクションも要旨も取得できなかった場合（スキャン PDF の可能性）、
        # OCRmyPDF でテキストレイヤーを付与してリトライする
        if not result.sections and not result.abstract:
            log.info(
                "grobid_task",
                "GROBID がテキスト抽出できず。OCRmyPDF でリトライします",
                paper_id=paper_id,
            )
            from app.providers.inference_client import get_ocr_client  # noqa: PLC0415

            ocr_client = await get_ocr_client()
            searchable_pdf = await ocr_client.ocr_pdf(pdf_bytes)
            if searchable_pdf:
                result = await grobid.process_fulltext_document(searchable_pdf)
                if not result:
                    log.warning(
                        "grobid_task", "OCRmyPDF 後も GROBID 解析失敗", paper_id=paper_id
                    )
                    storage.update_processing_status(paper_id, "grobid_status", "failed")
                    return
                log.info(
                    "grobid_task",
                    "OCRmyPDF リトライ後に GROBID 解析成功",
                    paper_id=paper_id,
                    sections=len(result.sections),
                )
            else:
                log.warning(
                    "grobid_task", "OCRmyPDF が使用不可のためリトライをスキップ", paper_id=paper_id
                )

        if result.title:
            storage.update_paper_title(paper_id, result.title)
        if result.authors:
            storage.update_paper_authors(paper_id, result.authors)
        if result.abstract:
            storage.update_paper_abstract(paper_id, result.abstract)

        # GROBID Markdown を grobid_text カラムに保存する。
        # ocr_text は "\n\n---\n\n" ページ区切りを維持するため上書きしない。
        grobid_md = grobid.build_markdown(result)
        if grobid_md:
            storage.update_paper_grobid_text(paper_id, grobid_md)
            log.info(
                "grobid_task",
                "GROBID Markdown を grobid_text に保存しました",
                paper_id=paper_id,
                md_len=len(grobid_md),
            )

        storage.update_processing_status(paper_id, "grobid_status", "success")
        log.info(
            "grobid_task",
            "GROBID エンリッチメント完了",
            paper_id=paper_id,
            title=result.title,
            sections=len(result.sections),
        )

    except Exception as e:
        storage.update_processing_status(paper_id, "grobid_status", "failed")
        log.error(
            "grobid_task",
            "GROBID エンリッチメント失敗",
            paper_id=paper_id,
            error=str(e),
            exc_info=True,
        )
    finally:
        storage.close()
