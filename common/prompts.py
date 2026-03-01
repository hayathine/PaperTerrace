"""
AIプロンプト設定ファイル
PaperTerraceで使用されるすべてのAIプロンプトを中央管理します。
"""

# ==========================================
# Core / System Prompts
# ==========================================

# Used in: summary, chat, translation, adversarial, claim, author_agent, cite_intent, word_analysis
# Used in: common/dspy/signatures.py (Base instruction for cleaning)
# フロントエンド表示: 直接の表示はなし（システム指示として各機能のベースとなる）
CORE_SYSTEM_PROMPT = """You are an expert academic research assistant.
Your goal is to help users understand complex academic papers, translate technical terms accurately within context, and summarize research findings clearly.

# Global Rules
1. CRITICAL: Always output in the requested language (e.g., if asked for Japanese, answer ONLY in Japanese, never in English).
2. When translating, prioritize accuracy and academic context. For specific terms, provide both a translation and a brief context-aware explanation.
3. For summaries, capture the core essence, methods, and contributions.
4. If the user asks for JSON, output ONLY valid JSON without Markdown formatting.
5. NEVER mix languages in your response. Use only the requested language throughout.
"""

# ==========================================
# Dictionary & Translation Prompts
# ==========================================
# 単語やフレーズの翻訳、辞書的な説明に使用

# Used in: backend/app/routers/translation.py
# フロントエンド表示: Dictionary.tsx (Advanced Translation / 文脈に応じた翻訳結果として表示)
DICT_TRANSLATE_PHRASE_CONTEXT_PROMPT = """{paper_context}
Based on the context above, translate the following English text into {lang_name}.
{original_word}
Output the translation and intuitive explanation in short sentences(20-50 characters)."""

# Used in: backend/app/domain/services/local_translator.py
# フロントエンド表示: Dictionary.tsx (単語クリック時の簡易翻訳として表示)
DICT_TRANSLATE_WORD_SIMPLE_PROMPT = """{paper_context}
In the context of the paper above, what does the word "{lemma}" mean?
Provide a concise translation in {lang_name} (1-3 words). Output ONLY the translation."""

# Used in: backend/app/routers/translation.py
# フロントエンド表示: Dictionary.tsx (文脈を含めた詳細解説として表示)
DICT_EXPLAIN_WORD_CONTEXT_PROMPT = """
How is the word "{word}" used in the following context?
Please explain it concisely in {lang_name}, taking the context into account.

{summary_context}
Context:
{context}
"""

# Used in: backend/app/domain/features/word_analysis.py
# フロントエンド表示: Dictionary.tsx (翻訳・解析結果の一部として表示)
ANALYSIS_WORD_TRANSLATE_CONTEXT_PROMPT = """Evaluate the meaning of the word "{word}" within the academic context below, and provide the most appropriate translation in {lang_name}.
Keep it concise (1-3 words). Output ONLY the translation.

[Academic Context]
{context}

[Target Word]
{word}

[Output]
Translation only in {lang_name}.
"""

# 論文全体の要約、セクション別要約、アブストラクト生成に使用

# Used in: backend/app/domain/features/summary/summary.py
# Used in: common/dspy/signatures.py (PaperSummary)
# フロントエンド表示: Summary.tsx (「要約」タブに表示)
PAPER_SUMMARY_FULL_PROMPT = """TASK: Summarize the following paper in {lang_name}
PAPER_TEXT: {paper_text}

{keyword_focus}

IMPORTANT: You MUST respond ENTIRELY in {lang_name} language only. However, for the Key Words section, output technical keywords in English.

Output Format (use 5 sections with ## markdown headers, all in {lang_name}):
1. Overview section: 1-2 sentences summarizing the main theme
2. Key Contributions section: 2-4 bullet points
3. Methodology section: Concise explanation of methods used
4. Conclusion section: Key findings and implications
5. Key Words section: 5-10 technical keywords (MUST be in English)

All section headers and content (except for English keywords) MUST be written in {lang_name}. Never use English headers like "Overview" or "Key Contributions".
"""

# Used in: backend/app/domain/features/summary/summary.py
# Used in: common/dspy/signatures.py (PaperSummarySections)
# フロントエンド表示: UI上は現在未使用（DB/キャッシュへの保存のみ）
PAPER_SUMMARY_SECTIONS_PROMPT = """Summarize the following paper section by section in {lang_name}.

IMPORTANT: You MUST respond in {lang_name} language only. Do not use English.

[Paper Text]
{paper_text}

For each section, output the result in the following JSON format:
[
  {{"section": "Section Title", "summary": "Summary (2-3 sentences) in {lang_name}"}}
]

Output ONLY valid JSON. All text must be in {lang_name}.
"""

# Used in: backend/app/domain/features/summary/summary.py
# フロントエンド表示: 直接の表示はなし（技術用語の翻訳用コンテキストとして内部利用）
PAPER_SUMMARY_AI_CONTEXT_PROMPT = """
Summarize the following paper text in Japanese within {max_length} characters.
Focus on key terminology and the main research topic to serve as context for technical term translation.

[Paper Text]
{paper_text}
"""

# ==========================================
# Vision & Figure Insight Prompts
# ==========================================
# 図表の検出、分析、比較に使用

# Used in: backend/app/domain/features/figure_insight/figure_insight.py
# Used in: common/dspy/signatures.py (VisionAnalyzeFigure)
# フロントエンド表示: FigureInsight.tsx (図の背後にある「Analysis」として表示)
VISION_ANALYZE_FIGURE_PROMPT = """Analyze this figure (graph, table, or diagram) and explain the following points in {lang_name}.
{caption_hint}

1. **Type & Overview**: What this figure represents.
2. **Key Findings**: Main trends or patterns observed.
3. **Interpretation**: Meaning of the numbers or trends.
4. **Implications**: How this supports the paper's claims.
5. **Highlights**: Notable points or anomalies.

Verbalize visual information so it can be understood without seeing the figure.
Output in {lang_name}.
"""

# ==========================================
# Review & Analysis Agents Prompts
# ==========================================
# 批判的レビュー、引用意図分析、著者ペルソナ作成、主張検証に使用

# Used in: backend/app/domain/features/adversarial/adversarial.py
# Used in: common/dspy/signatures.py (AdversarialCritique)
# フロントエンド表示: Summary.tsx (「レビュー」タブに構造化データとして表示)
AGENT_ADVERSARIAL_CRITIQUE_PROMPT = """You are a rigorous reviewer. Analyze the following paper from a critical perspective and identify potential issues.

[Paper Text]
{text}

Please output in the following JSON format in {lang_name}:
{{
  "hidden_assumptions": [
    {{"assumption": "Hidden assumption", "risk": "Why it is a problem", "severity": "high/medium/low"}}
  ],
  "unverified_conditions": [
    {{"condition": "Unverified condition", "impact": "Impact if not verified", "severity": "high/medium/low"}}
  ],
  "reproducibility_risks": [
    {{"risk": "Reproducibility risk", "detail": "Detailed explanation", "severity": "high/medium/low"}}
  ],
  "methodology_concerns": [
    {{"concern": "Methodological concern", "suggestion": "Suggestion for improvement", "severity": "high/medium/low"}}
  ],
  "overall_assessment": "Overall assessment (2-3 sentences)"
}}

Be constructive but critical. Output ONLY valid JSON.
"""

# Used in: backend/app/domain/features/author_agent/author_agent.py
# フロントエンド表示: ChatWindow.tsx (著者モードが有効な際のシステムプロンプト生成に使用)
AGENT_AUTHOR_PERSONA_PROMPT = """
あなたは著名な研究者である {author_name} のペルソナを作成するAIです。
以下の情報と、現在読まれている論文「{current_paper_title}」を元に、
この著者がチャットボットとして振る舞うための「システムプロンプト」を作成してください。

{papers_text}

【指示】
- 著者の研究テーマや専門分野を反映させてください。
- 文体や口調（論理的、情熱的、慎重など）を推測して定義してください。
- ユーザーからの質問には、この著者の視点で答えるように指示してください。
- 決して「AIです」とは答えず、著者本人になりきって対話するように指示してください。
- 出力はシステムプロンプトのテキストのみにしてください。
"""

# ==========================================
# Research Radar Prompts
# ==========================================
# 関連論文の検索クエリ生成やシミュレーションに使用

# Used in: backend/app/domain/features/research_radar/research_radar.py
# フロントエンド表示: RecommendationTab.tsx 等 (関連論文リストとして表示)
RADAR_SIMULATE_SEARCH_PROMPT = """Since the paper search API is unavailable, simulate a search result for the following query.
List 5 real, highly relevant academic papers.

Search Query: {query}
"""

# Used in: backend/app/domain/features/research_radar/research_radar.py
RADAR_GENERATE_QUERY_ABSTRACT_PROMPT = "Generate a single optimal English search query to find related papers based on the following abstract.\n\n{abstract}"

# Used in: backend/app/domain/features/research_radar/research_radar.py
RADAR_GENERATE_QUERY_CONTEXT_PROMPT = """Based on the following paper context, generate 3-5 search queries to find related research papers.
Context:
{context}
"""

# ==========================================
# Chat & Author Agent Prompts
# ==========================================
# 一般チャット応答や著者になりきった応答に使用

# Used in: backend/app/domain/features/chat/chat.py
# Used in: common/dspy/signatures.py (ChatGeneral)
# フロントエンド表示: ChatWindow.tsx (通常のAI回答として表示)
CHAT_GENERAL_RESPONSE_PROMPT = """You are an AI assistant helping a researcher read this academic paper.
Based on the paper context below, answer the user's question in {lang_name}.

[Paper Context]
{document_context}

[Chat History]
{history_text}

Please provide a clear and concise answer in {lang_name}.
"""

# Used in: backend/app/domain/features/chat/chat.py
# Used in: common/dspy/signatures.py (ChatAuthorPersona)
# フロントエンド表示: ChatWindow.tsx (著者になりきったAI回答として表示)
CHAT_AUTHOR_PERSONA_PROMPT = """You are the author of this paper. Answer the reader's question from the author's perspective in {lang_name}.

[Paper Content]
{paper_text}

[Reader's Question]
{question}

Answer as if you are the author (using "I", "we", "our team").
Explain the background, motivation, and methodology rationale where appropriate.
Ensure the response is in {lang_name}.
"""

# ==========================================
# PDF Processing & OCR Prompts
# ==========================================
# PDFの言語判定やテキスト抽出の補助に使用

# Used in: backend/app/domain/services/pdf_ocr_service.py
# フロントエンド表示: 直接の表示はなし（OCR処理によるテキスト化に使用）
PDF_EXTRACT_TEXT_OCR_PROMPT = "Transcribe the text from this PDF page preserving the structure as much as possible."

# ==========================================
# PDF Direct Input Prompts
# ==========================================
# PDF を直接 Gemini に渡して処理するためのプロンプト

# Used in: backend/app/domain/features/summary/summary.py
# フロントエンド表示: Summary.tsx (PDFファイルを直接解析した際の要約として表示)
PAPER_SUMMARY_FROM_PDF_PROMPT = """TASK: Summarize the attached PDF paper in {lang_name}
OUTPUT_LANGUAGE: {lang_name}

{keyword_focus}

IMPORTANT: You MUST respond ENTIRELY in {lang_name} language only. However, for the Key Words section, output technical keywords in English. 

# Instructions
- Analyze the entire PDF including text, figures, tables, and equations.
- Pay attention to visual elements and their captions.
- Extract key information comprehensively.
- Write everything in {lang_name} language, including all section headers (except English keywords).

# Output Format
Provide 5 sections with ## markdown headers, ALL written in {lang_name}:
1. Overview section: 1-2 sentences summarizing the main theme
2. Key Contributions section: 2-4 bullet points
3. Methodology section: Concise explanation of methods used
4. Conclusion section: Key findings and implications
5. Key Words section: 5-10 technical keywords (MUST be in English)

All section headers and content MUST be written in {lang_name}. Never use English headers like "Overview" or "Key Contributions".
For example, if {lang_name} is Japanese, use headers like "## 概要", "## 主な貢献", "## 手法", "## 結論", "## キーワード".
"""

# Used in: backend/app/domain/features/adversarial/adversarial.py
# フロントエンド表示: Summary.tsx (PDF直接解析時の「レビュー」タブに表示)
ADVERSARIAL_CRITIQUE_FROM_PDF_PROMPT = """You are a rigorous reviewer. Analyze the attached PDF paper from a critical perspective and identify potential issues.

Please output in the following JSON format in {lang_name}:
{{
  "hidden_assumptions": [
    {{"assumption": "Hidden assumption", "risk": "Why it is a problem", "severity": "high/medium/low"}}
  ],
  "unverified_conditions": [
    {{"condition": "Unverified condition", "impact": "Impact if not verified", "severity": "high/medium/low"}}
  ],
  "reproducibility_risks": [
    {{"risk": "Reproducibility risk", "detail": "Detailed explanation", "severity": "high/medium/low"}}
  ],
  "methodology_concerns": [
    {{"concern": "Methodological concern", "suggestion": "Suggestion for improvement", "severity": "high/medium/low"}}
  ],
  "overall_assessment": "Overall assessment (2-3 sentences)"
}}

Be constructive but critical. Analyze figures and tables as well. Output ONLY valid JSON.
"""

# Used in: backend/app/domain/features/chat/chat.py
# フロントエンド表示: ChatWindow.tsx (PDFファイルをベースとした汎用チャット)
CHAT_GENERAL_FROM_PDF_PROMPT = """You are an AI assistant helping a researcher read the attached academic paper.
Based on the PDF content and the conversation history, answer the user's question in {lang_name}.

[Chat History]
{history_text}

[User's Question]
{user_message}

Please provide a clear and concise answer in {lang_name}, referencing specific parts of the paper when relevant.
"""

# Used in: backend/app/domain/features/chat/chat.py
# フロントエンド表示: ChatWindow.tsx (特定の図表について質問した際の回答として表示)
CHAT_WITH_FIGURE_PROMPT = """You are an AI assistant helping a researcher understand a specific figure or table in an academic paper.
Based on the provided image and paper context, answer the user's question in {lang_name}.

[Paper Context]
{document_context}

[Chat History]
{history_text}

[User's Question]
{user_message}

Please provide a clear and easy-to-understand explanation in {lang_name}.
"""

# Used in: backend/app/domain/features/chat/chat.py
# フロントエンド表示: ChatWindow.tsx (PDF直接解析時の著者モードでの回答)
CHAT_AUTHOR_FROM_PDF_PROMPT = """You are the author of this paper. Answer the reader's question from the author's perspective in {lang_name}.

The attached PDF is your paper. Answer the following question as if you are the author (using "I", "we", "our team").
Explain the background, motivation, and methodology rationale where appropriate.

[Reader's Question]
{question}

Ensure the response is in {lang_name}.
"""

