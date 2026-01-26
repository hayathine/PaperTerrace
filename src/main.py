import httpx
from bs4 import BeautifulSoup, UnicodeDammit
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# logic.pyで定義したクラス/関数をインポート（前回の回答のロジックを含む想定）
from .feature.word_focus import EnglishAnalysisService

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")
service = EnglishAnalysisService()


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def format_results_to_html(words: list) -> str:
    """解析結果をHTMLテーブルに変換する"""
    rows = ""
    for item in words:
        source_color = (
            "bg-blue-100 text-blue-800"
            if item["source"] == "Jamdict"
            else "bg-purple-100 text-purple-800"
        )
        rows += f"""
        <tr class="border-b hover:bg-gray-50">
            <td class="px-4 py-2 font-medium">{item["original"]}</td>
            <td class="px-4 py-2">{item["definition"]}</td>
            <td class="px-4 py-2 text-xs">
                <span class="{source_color} px-2 py-1 rounded-full font-semibold">{item["source"]}</span>
            </td>
        </tr>
        """

    return f"""
    <div class="mt-8">
        <h3 class="text-2xl font-bold mb-4">Vocabulary List</h3>
        <div class="overflow-x-auto">
            <table class="min-w-full bg-white border border-gray-200">
                <thead class="bg-gray-100">
                    <tr>
                        <th class="px-4 py-2 text-left">Word</th>
                        <th class="px-4 py-2 text-left">Meaning (JA)</th>
                        <th class="px-4 py-2 text-left">Source</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    """


@app.get("/explain/{lemma}", response_class=HTMLResponse)
async def explain(lemma: str):
    # 特定の1単語だけを詳しく解説
    html = await service.explain_word(lemma)
    return html


@app.post("/analyze_txt", response_class=HTMLResponse)
async def analyze_txt(html_text: str = Form(...)):
    # 形態素解析だけして、クリック可能なHTMLを返す
    ruby_html = service.tokenize_to_html(html_text)
    return f'<div class="leading-relaxed tracking-wide">{ruby_html}</div>'


# @app.post("/analyze-pdf", response_class=HTMLResponse)
# async def analyze_pdf(file: UploadFile = File(...)):
#     content = await file.read()
#     pdf_ext = PDFExtractor()
#     raw_text = pdf_ext.extract_text(content)

#     if not raw_text.strip():
#         return '<div class="text-red-500">PDFからテキストを抽出できませんでした。</div>'

#     word_list = await service.tokenize_to_html(raw_text)
#     return format_results_to_html(word_list)


@app.post("/analyze-url", response_class=HTMLResponse)
async def analyze_url(url: str = Form(...)):
    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
        except Exception as e:
            return f'<div class="text-red-500">Error: {str(e)}</div>'

    # 文字コード判定とデコード
    dammit = UnicodeDammit(response.content, is_html=True)
    raw_html = dammit.unicode_markup or response.content.decode(
        "utf-8", errors="replace"
    )

    # --- 重要：HTMLから純粋なテキストだけを抽出 ---
    soup = BeautifulSoup(raw_html, "html.parser")

    # スクリプトやスタイルシートを除去
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    clean_text = soup.get_text(separator=" ")  # タグの間にスペースを入れて結合

    # メソッド名を更新
    ruby_html = await service.tokenize_to_html(clean_text)
    return f'<div class="leading-relaxed tracking-wide">{ruby_html}</div>'
