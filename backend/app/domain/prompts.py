"""
AIプロンプト設定ファイル
PaperTerraceで使用されるすべてのAIプロンプトを中央管理します。
"""

# ==========================================
# Core / System Prompts
# ==========================================

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

DICT_TRANSLATE_PHRASE_CONTEXT_PROMPT = """{paper_context}
Based on the context above, translate the following English text into {lang_name}.
{original_word}
Output the translation and intuitive explanation."""

DICT_TRANSLATE_WORD_SIMPLE_PROMPT = """{paper_context}
In the context of the paper above, what does the word "{lemma}" mean?
Provide a concise translation in {lang_name} (1-3 words). Output ONLY the translation."""

DICT_EXPLAIN_WORD_CONTEXT_PROMPT = """
How is the word "{word}" used in the following context?
Please explain it concisely in {lang_name}, taking the context into account.

{summary_context}
Context:
{context}
"""

ANALYSIS_BATCH_TRANSLATE_PROMPT = """Provide concise translations for the following English words in {lang_name}.
Output format per line: "Word: Translation"
Keep it very brief (1-2 words).

Words:
{words_list}"""

ANALYSIS_WORD_TRANSLATE_CONTEXT_PROMPT = """Evaluate the meaning of the word "{word}" within the academic context below, and provide the most appropriate translation in {lang_name}.
Keep it concise (1-3 words). Output ONLY the translation.

[Academic Context]
{context}

[Target Word]
{word}

[Output]
Translation only in {lang_name}.
"""

# ==========================================
# Chat Specialized Prompts
# ==========================================

DICT_AI_CHAT_TRANSLATE_PROMPT = """You are an academic translation expert.
The user wants to understand a specific term/phrase in the context of this research paper.
Please provide:
1. An accurate Japanese translation that fits the academic context.
2. A very brief (1-2 sentences) explanation of why this term is used or what it implies in this specific context.

[Term/Phrase]
{word}

[Paper Context]
{document_context}
"""
# 論文全体の要約、セクション別要約、アブストラクト生成に使用

PAPER_SUMMARY_FULL_PROMPT = """TASK: Summarize the following paper in {lang_name}
PAPER_TEXT: {paper_text}

IMPORTANT: You MUST respond in {lang_name} language only. Do not use English.

Overview: (1-2 sentences summarizing the main theme)
Key Contributions: (2-4 bullet points)
Methodology: (Concise explanation of methods used)
Conclusion: (Key findings and implications)
"""

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

PAPER_SUMMARY_ABSTRACT_PROMPT = """Create an abstract of the following paper in {lang_name}.
(Length: approx. 100-200 words or equivalent characters)

{paper_text}

Write in a concise, academic style in {lang_name}.
"""

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

VISION_DETECT_ITEMS_PROMPT = """Analyze the following image of a document page and identify all figures, tables, and independent mathematical equations.

Return a JSON list of bounding boxes for each detected item:
[
  {"label": "figure" | "table" | "equation", "box_2d": [ymin, xmin, ymax, xmax]}
]

[Instructions]
- Coordinates must be normalized (0.0 to 1.0).
- "figure": Graphs, charts, diagrams, photos.
- "table": Tabular data structures.
- "equation": Significant mathematical formulas/equations displayed independently (not inline).
- Ignore small icons, headers, footers, or page numbers.
- Combine the figure image and its caption into one box if possible, or just the figure.
- If no items are found, return an empty list [].
"""

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

VISION_ANALYZE_TABLE_PROMPT = """Analyze the following table and explain it in {lang_name}.
{context_hint}

[Table Content]
{table_text}

Please explain:
1. Overview of what the table shows.
2. Key numbers and trends.
3. Notable comparisons or differences.
4. Conclusions drawn from this table.

Output in {lang_name}.
"""

VISION_COMPARE_FIGURES_PROMPT = """Compare the following two figures and analyze their relationship or differences in {lang_name}.

[Figure 1]
{description1}

[Figure 2]
{description2}

Comparison Points:
1. Similarities
2. Differences
3. Complementary relationship
4. Contradictions (if any)

Output in {lang_name}.
"""

VISION_ANALYZE_EQUATION_PROMPT = """Analyze this area of the research paper and determine if it contains a mathematical equation.
If it is an equation, convert it to valid LaTeX format.

Input: Image or crop from a PDF page.

Output only valid JSON in the following format:
{{
    "is_equation": boolean,
    "confidence": float (0-1),
    "latex": "The LaTeX representation of the equation",
    "explanation": "Brief explanation of what the equation represents in {lang_name}"
}}

Notes:
- If multiple equations are present, include them in a single block or multiple lines in the 'latex' field.
- If it is not an equation (e.g., just random text or an image), set "is_equation" to false.
"""

# ==========================================
# Review & Analysis Agents Prompts
# ==========================================
# 批判的レビュー、引用意図分析、著者ペルソナ作成、主張検証に使用

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

AGENT_CITE_INTENT_PROMPT = """Identify and analyze all "citations" (references to other works) in the following academic text, and classify the intent of each citation.

[Text]
{paragraph}

[Classification Criteria]
- Support: The author supports the findings of the previous research or uses it as evidence for their own claims (e.g., "consistent with", "provides evidence for").
- Use: The author uses/adopts a method, data, software, theory, or tool from the previous research (e.g., "following X", "based on data from Y").
- Contrast: The author compares or contrasts their findings/methods with the previous research (e.g., "in contrast to", "unlike previous work").
- Criticize: The author points out flaws, limitations, or errors in the previous research, or argues against it (e.g., "however, X failed to", "a limitation of").
- Neutral: The author mentions the research as background or context without explicit evaluation or dynamic usage.

[Instructions]
1. Identify the citation strings (e.g., [1], Author et al. (2020), etc.) from the text.
2. Select the most appropriate category from the 5 categories above.
3. Write a brief reason for the classification in {lang_name}.
"""

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

AGENT_CLAIM_VERIFY_PROMPT = """You are an autonomous "Evidence Checker".
Your task is to critically verify the claims made in the following text by cross-referencing with external information (Web Search).

[Target Text]
{paragraph}

[Instructions]
1. Identify the core claims (e.g., "Outperforms SOTA by 10%", "New architecture X").
2. AUTONOMOUSLY SEARCH for these claims online. Look for:
   - Reproducibility reports (GitHub issues, Twitter discussions, Reddit threads).
   - Contradictory papers (Google Scholar).
   - Consensus in the community.
3. Report your findings in {lang_name}.
"""

# ==========================================
# Research Radar Prompts
# ==========================================
# 関連論文の検索クエリ生成やシミュレーションに使用

RADAR_SIMULATE_SEARCH_PROMPT = """Since the paper search API is unavailable, simulate a search result for the following query.
List 5 real, highly relevant academic papers.

Search Query: {query}
"""

RADAR_GENERATE_QUERY_ABSTRACT_PROMPT = "Generate a single optimal English search query to find related papers based on the following abstract.\n\n{abstract}"

RADAR_GENERATE_QUERY_CONTEXT_PROMPT = """Based on the following paper context, generate 3-5 search queries to find related research papers.
Context:
{context}
"""

# ==========================================
# Chat & Author Agent Prompts
# ==========================================
# 一般チャット応答や著者になりきった応答に使用

CHAT_GENERAL_RESPONSE_PROMPT = """You are an AI assistant helping a researcher read this academic paper.
Based on the paper context below, answer the user's question in {lang_name}.

[Paper Context]
{document_context}

[Chat History]
{history_text}

Please provide a clear and concise answer in {lang_name}.
"""

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

PDF_DETECT_LANGUAGE_PROMPT = """Identify the primary language of the following text and return ONLY the ISO 639-1 code (e.g., 'en', 'ja', 'fr').
Text Sample:
{text}
"""

PDF_EXTRACT_TEXT_OCR_PROMPT = "Transcribe the text from this PDF page preserving the structure as much as possible."

# ==========================================
# PDF Direct Input Prompts
# ==========================================
# PDF を直接 Gemini に渡して処理するためのプロンプト

PAPER_SUMMARY_FROM_PDF_PROMPT = """TASK: Summarize the attached PDF paper in {lang_name}
OUTPUT_LANGUAGE: {lang_name}

IMPORTANT: You MUST respond in {lang_name} language only. Do not use English.

# Instructions
- Analyze the entire PDF including text, figures, tables, and equations.
- Pay attention to visual elements and their captions.
- Extract key information comprehensively.
- Write everything in {lang_name} language.

# Output Format
Provide the following in {lang_name}:

## Overview
(1-2 sentences summarizing the main theme in {lang_name})

## Key Contributions
- (2-4 bullet points in {lang_name})

## Methodology
(Concise explanation of methods used in {lang_name})

## Conclusion
(Key findings and implications in {lang_name})

Do not use English in the output.
"""

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

CHAT_GENERAL_FROM_PDF_PROMPT = """You are an AI assistant helping a researcher read the attached academic paper.
Based on the PDF content and the conversation history, answer the user's question in {lang_name}.

[Chat History]
{history_text}

[User's Question]
{user_message}

Please provide a clear and concise answer in {lang_name}, referencing specific parts of the paper when relevant.
"""

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

CHAT_AUTHOR_FROM_PDF_PROMPT = """You are the author of this paper. Answer the reader's question from the author's perspective in {lang_name}.

The attached PDF is your paper. Answer the following question as if you are the author (using "I", "we", "our team").
Explain the background, motivation, and methodology rationale where appropriate.

[Reader's Question]
{question}

Ensure the response is in {lang_name}.
"""

CLAIM_VERIFY_FROM_PDF_PROMPT = """You are an autonomous "Evidence Checker".
Your task is to critically verify the claims made in the attached PDF by cross-referencing with external information (Web Search).

[Instructions]
1. Identify the core claims in this paper (e.g., "Outperforms SOTA by 10%", "New architecture X").
2. AUTONOMOUSLY SEARCH for these claims online. Look for:
   - Reproducibility reports (GitHub issues, Twitter discussions, Reddit threads).
   - Contradictory papers (Google Scholar).
   - Consensus in the community.
3. Report your findings in {lang_name}.

Output should be comprehensive and cite sources where possible.
"""
