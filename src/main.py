import asyncio
import uuid

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .logic import EnglishAnalysisService  # インポート元を修正

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")
service = EnglishAnalysisService()
text_storage = {}  # SSE用の一時保存


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/explain/{lemma}")
async def explain(lemma: str):
    return await service.explain_word(lemma)


@app.post("/analyze_txt")
async def analyze_txt(html_text: str = Form(...)):
    task_id = str(uuid.uuid4())
    text_storage[task_id] = html_text
    return HTMLResponse(
        f'<div hx-ext="sse" sse-connect="/stream/{task_id}" sse-swap="message"\
              hx-swap="beforeend"></div>'
    )


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    # ファイル名がない、またはサイズが0の場合はエラーを返す
    if not file.filename or file.size == 0:

        async def error_stream():
            yield (
                "data: <div class='p-6 bg-amber-50 border-2 border-amber-200 rounded-2xl text-amber-700 animate-fade-in'>"
                "<h3 class='font-bold mb-2'>⚠️ ファイルが未選択です</h3>"
                "<p class='text-xs opacity-80'>解析するPDFファイルをアップロードしてください。</p>"
                "</div>\n\n"
            )

        return StreamingResponse(error_stream(), media_type="text/event-stream")
    content = await file.read()

    # AI OCR を実行
    raw_text = await service.ocr_service.extract_text_with_ai(content, file.filename)

    # APIエラーが返ってきた場合の処理
    if raw_text.startswith("ERROR_API_FAILED:"):
        error_detail = raw_text.replace("ERROR_API_FAILED: ", "")

        async def error_stream():
            # Tailwindを使ったリッチなエラー表示を送信
            yield (
                f"data: <div class='p-6 bg-red-50 border-2 border-red-200 rounded-2xl\
                      text-red-700 animate-fade-in'>"
                f"<h3 class='font-bold mb-2'>⚠️ AI解析エラー</h3>"
                f"<p class='text-xs opacity-80 mb-4'>APIの呼び出しに失敗しました。\
                    モデル名やAPIキーを確認してください。</p>"
                f"<div class='bg-white/50 p-3 rounded-lg \
                    font-mono text-[10px] break-all'>{error_detail}</div>"
                f"</div>\n\n"
            )

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # 正常な場合はIDを発行してストリームへ（既存のロジック）
    task_id = str(uuid.uuid4())
    text_storage[task_id] = raw_text
    return HTMLResponse(
        f'<div hx-ext="sse" sse-connect="/stream/{task_id}" sse-swap="message" \
            hx-swap="beforeend"></div>'
    )


@app.get("/stream/{task_id}")
async def stream(task_id: str):
    text = text_storage.get(task_id, "")

    async def generate():
        async for chunk in service.tokenize_stream(text):
            yield chunk
            await asyncio.sleep(0.01)
        if task_id in text_storage:
            del text_storage[task_id]

    return StreamingResponse(generate(), media_type="text/event-stream")
