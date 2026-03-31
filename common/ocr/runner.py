"""
OCRmyPDF ランナー

ProcessPoolExecutor で pickle 可能にするため、モジュールレベル関数として定義する。
inference-service の TesseractOcrService から呼び出される。

ocrmypdf は inference-service の依存関係にのみ含まれるため、
実行は必ず inference-service 環境で行われる（lazy import で対応）。
"""


def ocrmypdf_run(pdf_bytes: bytes, lang: str) -> bytes:
    """
    OCRmyPDF でスキャン PDF にテキストレイヤーを付与してサーチャブル PDF を返す。

    ProcessPoolExecutor でサブプロセス実行するため、モジュールレベルで定義する
    （クラス内のネスト関数は pickle 不可のため）。

    Args:
        pdf_bytes: 入力 PDF のバイト列
        lang: Tesseract 言語コード（例: "eng", "jpn"）
    Returns:
        テキストレイヤー付き PDF のバイト列
    """
    import io
    import ocrmypdf  # noqa: PLC0415 — inference-service 環境のみで実行される

    input_buf = io.BytesIO(pdf_bytes)
    output_buf = io.BytesIO()
    ocrmypdf.ocr(
        input_buf,
        output_buf,
        language=lang,
        skip_text=True,        # テキストレイヤー済みのページはスキップ
        progress_bar=False,
        optimize=0,            # 速度優先（圧縮最適化なし）
        output_type="pdf",
        jobs=4,                # CPU limit=6 に合わせ4並列（各ワーカーが十分なCPUを確保）
        tesseract_timeout=60,  # 1ページあたり60秒でスキップ（ゾンビ防止）
    )
    return output_buf.getvalue()
