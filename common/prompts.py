"""
AIプロンプト設定ファイル
PaperTerraceで使用されるすべてのAIプロンプトを中央管理します。
"""

# ==========================================
# Core / System Prompts
# ==========================================

# Used in: summary, chat, translation, adversarial, claim, cite_intent, word_analysis
# Used in: common/dspy/signatures.py (Base instruction for cleaning)
# フロントエンド表示: 直接の表示はなし（システム指示として各機能のベースとなる）
CORE_SYSTEM_PROMPT = """You are an expert academic research assistant.
Your goal is to help users understand complex academic papers, translate technical terms accurately within context, and summarize research findings clearly.

# Global Rules
1. CRITICAL: Always output in the requested language (e.g., if asked for Japanese, answer in Japanese). However, maintain original notation for proper nouns, acronyms, and technical terms that are commonly used as-is in that language's academic community.
2. When translating, prioritize accuracy and academic context. For specific terms, provide both a translation (or original term if appropriate) and a brief context-aware explanation.
3. capture the core essence, methods, and contributions in summaries.
4. If the user asks for JSON, output ONLY valid JSON without Markdown formatting.
5. Do NOT add meta-comments like "(そのまま)" or "(Translation: ...)" to the output.
"""

# ==========================================
# Dictionary & Translation Prompts
# ==========================================
# 単語やフレーズの翻訳、辞書的な説明に使用

# Used in: common/dspy/signatures.py (ContextAwareTranslation)
# フロントエンド表示: Dictionary.tsx (文脈に適した翻訳・解説として表示)
DICT_TRANSLATE_QWEN_PROMPT = """[Academic Context]
{paper_context}

[Target Text]
{target_word}

Based on the context above, translate the English text into {lang_name}.
Output ONLY the translated word.

Examples:
- Context: We found a significant correlation between the two variables.
  Target: significant
  Language: Japanese
  Output: 有意な
- Context: Our approach outperforms existing SOTA models.
  Target: SOTA
  Language: Japanese
  Output: 最先端の
- Context: Large Language Models (LLMs) have revolutionized the field.
  Target: LLMs
  Language: Japanese
  Output: 大規模言語モデル"""


# Used in: backend/app/routers/translation.py
# フロントエンド表示: Dictionary.tsx (単語クリック時の簡易翻訳として表示)
DICT_TRANSLATE_WORD_SIMPLE_PROMPT = """{paper_context}
In the context of the paper above, what does the word "{target_word}" mean?
Provide a concise translation in {lang_name} (1-3 words). Output ONLY the translation."""

# Used in: common/dspy/signatures.py (DeepExplanation)
# フロントエンド表示: Dictionary.tsx (文脈を含めた詳細解説として表示)
DICT_EXPLAIN_GEMINI_PROMPT = """
TASK: Explain the following word or phrase in the context of the academic paper provided.

INSTRUCTIONS:
1. Provide a concise but insightful explanation in {lang_name}.
2. Do NOT just translate the word. Focus on its specific meaning, role, or technical significance within this paper.
3. If it is a technical term, explain the underlying concept briefly.
4. If it refers to a methodology or result, explain its importance.

{summary_context}

[Context]
{context}

[Target Word/Phrase]
{target_word}
"""

# Used in: backend/app/domain/features/word_analysis.py
# フロントエンド表示: Dictionary.tsx (翻訳・解析結果の一部として表示)
ANALYSIS_WORD_TRANSLATE_CONTEXT_PROMPT = """Evaluate the meaning of the word "{target_word}" within the academic context below, and provide the most appropriate translation in {lang_name}.
Keep it concise (1-3 words). Output ONLY the translation.

[Academic Context]
{context}

[Target Word]
{target_word}

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
Keep the total output concise (aim for under 1000 tokens).

Output Format (use 5 sections with ## markdown headers, all in {lang_name}):
1. Overview section: 1-2 sentences summarizing the main theme
2. Key Contributions section: 2-4 clear bullet points
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
Summarize the following paper text in {lang_name} within {max_length} characters.
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

# Used in: common/dspy/signatures.py (PaperRecommendation)
# フロントエンド表示: 推薦タブなどで「AIによる推薦理由」として表示
RECOMMENDATION_PAPER_PROMPT = """
Based on the user's knowledge level, interests, and unknown concepts, recommend the next papers they should read.
- Provide at least 3 recommended papers.
- Generate at least 2 search queries for Semantic Scholar.
- For beginner users, including survey papers is preferred.
"""

# Used in: common/dspy/signatures.py (UserProfileEstimation)
# フロントエンド表示: 直接の表示はなし（推薦ロジックの内部データとして利用）
RECOMMENDATION_USER_PROFILE_PROMPT = """
Estimate the user's understanding, interests, and unknown concepts from their behavioral data.
- Knowledge level (Beginner / Intermediate / Advanced)
- Extract interesting topics
- Identify concepts the user might not understand
- Direction of recommendation (Deep dive / Broadening / Application / Fundamentals)
"""

# Used in: backend/app/domain/features/adversarial/adversarial.py
# Used in: common/dspy/signatures.py (AdversarialCritique)
# フロントエンド表示: Summary.tsx (「レビュー」タブに構造化データとして表示)
AGENT_ADVERSARIAL_CRITIQUE_PROMPT = """You are a rigorous reviewer. Analyze the following paper from a critical perspective and identify potential issues.

[Paper Text]
{text}

Please output in the following JSON format in {lang_name}.
IMPORTANT: Limit each category (hidden_assumptions, unverified_conditions, etc.) to a maximum of 3 most significant items. Keep descriptions concise to ensure the total response is under 1000 tokens.

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
  "overall_assessment": "Short overall assessment (2-3 sentences)"
}}

Be constructive but critical. Output ONLY valid JSON.
"""

# ==========================================
# Chat Prompts
# ==========================================
# 一般チャット応答に使用

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
- Extract key information comprehensively but concisely.
- Write everything in {lang_name} language, including all section headers (except English keywords).

# Output Format
Provide 5 sections with ## markdown headers, ALL written in {lang_name}:
1. Overview section: 1-2 sentences summarizing the main theme
2. Key Contributions section: 2-4 clear bullet points
3. Methodology section: Concise explanation of methods used
4. Conclusion section: Key findings and implications
5. Key Words section: 5-10 technical keywords (MUST be in English)

All section headers and content MUST be written in {lang_name}. Never use English headers like "Overview" or "Key Contributions".
For example, if {lang_name} is Japanese, use headers like "## 概要", "## 主な貢献", "## 手法", "## 結論", "## キーワード".
"""

# Used in: backend/app/domain/features/adversarial/adversarial.py
# フロントエンド表示: Summary.tsx (PDF直接解析時の「レビュー」タブに表示)
ADVERSARIAL_CRITIQUE_FROM_PDF_PROMPT = """You are a rigorous reviewer. Analyze the attached PDF paper from a critical perspective and identify potential issues.

Please output in the following JSON format in {lang_name}.
IMPORTANT: Limit each category (hidden_assumptions, unverified_conditions, etc.) to a maximum of 3 most significant items. Keep descriptions concise to ensure the total response is under 1000 tokens.

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
  "overall_assessment": "Short overall assessment (2-3 sentences)"
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

USER_PERSONA_PROMPT = """You are user persona of a paper terrace user.


Please provide a user persona from trajectory.
"""
