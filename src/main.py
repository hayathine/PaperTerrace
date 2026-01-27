import asyncio

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# logic.pyで定義したクラス/関数をインポート（前回の回答のロジックを含む想定）
from .feature.dict import EnglishAnalysisService

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")
service = EnglishAnalysisService()


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/explain/{lemma}", response_class=HTMLResponse)
async def explain(lemma: str):
    # 特定の1単語だけを詳しく解説
    html = await service.explain_word(lemma)
    return html


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename

    # AI OCR を実行（内部でSQLiteキャッシュをチェック）
    raw_text = await service.ocr_service.extract_text_with_ai(content, filename)

    # ストリーミング開始
    async def stream():
        # ここで、以前作った task_id 発行 & GETストリーム 方式に繋げるとより安定します
        async for chunk in service.tokenize_stream(raw_text):
            yield chunk
            await asyncio.sleep(0.01)

    return StreamingResponse(stream(), media_type="text/event-stream")
