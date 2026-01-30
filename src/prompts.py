"""
Prompts configuration file.
Centralized location for all AI prompts used in PaperTerrace.
"""

# ==========================================
# System Prompt
# ==========================================

SYSTEM_PROMPT = """You are an expert academic research assistant.
Your goal is to help users understand complex academic papers, translate technical terms accurately within context, and summarize research findings clearly.

# Global Rules
1. Always output in the requested language (e.g., if asked for Japanese, answer in Japanese).
2. Maintain a professional, objective, and academic tone.
3. When translating, prioritize accuracy and academic context over literal translation.
4. For summaries, capture the core essence, methods, and contributions.
5. If the user asks for JSON, output ONLY valid JSON without Markdown formatting.
6. No intro/outro.
"""

# ==========================================
# Translation & Dictionary Prompts
# ==========================================

TRANSLATE_PHRASE_WITH_CONTEXT_PROMPT = """{paper_context}
Based on the context above, translate the following English text into {lang_name}.
{original_word}
Output the translation and intuitive explanation."""

TRANSLATE_WORD_SIMPLE_PROMPT = """{paper_context}
In the context of the paper above, what does the word "{lemma}" mean?
Provide a concise translation in {lang_name} (1-3 words). Output ONLY the translation."""

TRANSLATE_WORD_WITH_CONTEXT_EXPLAIN_PROMPT = """
How is the word "{word}" used in the following context?
Please explain it concisely in {lang_name}, taking the context into account.

{summary_context}
Context:
{context}
"""
TRANSLATE_BATCH_PROMPT = """Provide concise translations for the following English words in {lang_name}.
Output format per line: "Word: Translation"
Keep it very brief (1-2 words).

Words:
{words_list}"""

TRANSLATE_CONTEXT_AWARE_SIMPLE_PROMPT = """Evaluate the meaning of the word "{word}" within the academic context below, and provide the most appropriate translation in {lang_name}.
Keep it concise (1-3 words). Output ONLY the translation.

[Academic Context]
{context}

[Target Word]
{word}

[Output]
Translation only in {lang_name}.
"""

TRANSLATE_GENERAL_PROMPT = """Translate the English word or phrase "{word}" to {lang_name}.
Provide only the translation, nothing else. If it's a technical term, include a brief explanation in parentheses."""

TRANSLATE_PHRASE_GENERAL_PROMPT = """Translate the following English text to {lang_name}:

"{phrase}"

Provide only the translation, maintaining the original meaning and nuance. Output ONLY the translation."""

# ==========================================
# Summary Prompts
# ==========================================

SUMMARY_FULL_PROMPT = """Summarize the following paper in {lang_name}.

[Paper Text]
{paper_text}

Format the summary as follows in {lang_name}:

## Overview
(1-2 sentences summarizing the main theme)

## Key Contributions
(3-5 bullet points)

## Methodology
(Concise explanation of methods used)

## Conclusion
(Key findings and implications)
"""

SUMMARY_SECTIONS_PROMPT = """Summarize the following paper section by section in {lang_name}.

[Paper Text]
{paper_text}

For each section, output the result in the following JSON format:
[
  {{"section": "Section Title", "summary": "Summary (2-3 sentences) in {lang_name}"}}
]

Output ONLY valid JSON.
"""

SUMMARY_ABSTRACT_PROMPT = """Create an abstract of the following paper in {lang_name}.
(Length: approx. 100-200 words or equivalent characters)

{paper_text}

Write in a concise, academic style in {lang_name}.
"""

SUMMARY_CONTEXT_PROMPT = """
Summarize the following paper text in Japanese within {max_length} characters.
Focus on key terminology and the main research topic to serve as context for technical term translation.

[Paper Text]
{paper_text}
"""

# ==========================================
# Paragraph Explanation Prompts
# ==========================================

EXPLAIN_PARAGRAPH_PROMPT = """Please analyze and explain the following paragraph in detail.
{context_hint}
[Target Paragraph]
{paragraph}

Please provide a clear and easy-to-understand explanation in {lang_name}, covering the following points:

1. **Main Claim**: The core argument or content of this paragraph.
2. **Background Knowledge**: Prerequisites or technical terms needed to understand this.
3. **Logic Flow**: How the argument or logic is developed.
4. **Key Points**: Important implications or things to note.

Even if the content is highly technical, please explain it at a level understandable by a graduate student.
Ensure the output is in {lang_name}.
"""

TRANSLATE_PARAGRAPH_PROMPT = """Translate the following academic paragraph into naturally flowing {lang_name}.
Do not summarize or explain; provide a direct translation.
Maintain the original tone and nuance.

{context_hint}

[Target Paragraph]
{paragraph}

Output ONLY the translation.
"""


# ==========================================
# Figure Insight Prompts
# ==========================================

# ==========================================
# Figure Insight Prompts
# ==========================================

DETECT_FIGURES_PROMPT = """Analyze the following image of a document page and identify all figures, tables, and independent mathematical equations.

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

FIGURE_ANALYSIS_PROMPT = """Analyze this figure (graph, table, or diagram) and explain the following points in {lang_name}.
{caption_hint}

1. **Type & Overview**: What this figure represents.
2. **Key Findings**: Main trends or patterns observed.
3. **Interpretation**: Meaning of the numbers or trends.
4. **Implications**: How this supports the paper's claims.
5. **Highlights**: Notable points or anomalies.

Verbalize visual information so it can be understood without seeing the figure.
Output in {lang_name}.
"""

TABLE_ANALYSIS_PROMPT = """Analyze the following table and explain it in {lang_name}.
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

FIGURE_COMPARISON_PROMPT = """Compare the following two figures and analyze their relationship or differences in {lang_name}.

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

# ==========================================
# Adversarial Review Prompts
# ==========================================

ADVERSARIAL_CRITIQUE_PROMPT = """You are a rigorous reviewer. Analyze the following paper from a critical perspective and identify potential issues.

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

ADVERSARIAL_LIMITATIONS_PROMPT = """Identify limitations in the following paper that may not be explicitly stated by the authors.

[Paper Text]
{text}

Output in the following JSON format in {lang_name}:
[
  {{
    "limitation": "Explanation of limitation",
    "evidence": "Basis for this judgment",
    "impact": "Impact on research results",
    "severity": "high/medium/low"
  }}
]

Max 5 items. Output ONLY valid JSON.
"""

ADVERSARIAL_COUNTERARGUMENTS_PROMPT = """Generate 3 potential counterarguments to the following claim in {lang_name}.
{context_hint}

[Claim]
{claim}

Provide constructive and academic counterarguments, 2-3 sentences each.
Output as a numbered list.
"""

# ==========================================
# Research Radar Prompts
# ==========================================

RADAR_SIMULATE_SEARCH_PROMPT = """Since the paper search API is unavailable, simulate a search result for the following query.
List 5 real, highly relevant academic papers.

Search Query: {query}
"""

RADAR_QUERY_FROM_ABSTRACT_PROMPT = "Generate a single optimal English search query to find related papers based on the following abstract.\n\n{abstract}"

RADAR_QUERY_FROM_CONTEXT_PROMPT = """Based on the following paper context, generate 3-5 search queries to find related research papers.
Context:
{context}
"""

# ==========================================
# Chat Prompts
# ==========================================

CHAT_RESPONSE_PROMPT = """You are an AI assistant helping a researcher read this academic paper.
Based on the paper context below, answer the user's question in {lang_name}.

[Paper Context]
{document_context}

[Chat History]
{history_text}

Please provide a clear and concise answer in {lang_name}.
"""

CHAT_AUTHOR_AGENT_PROMPT = """You are the author of this paper. Answer the reader's question from the author's perspective in {lang_name}.

[Paper Content]
{paper_text}

[Reader's Question]
{question}

Answer as if you are the author (using "I", "we", "our team").
Explain the background, motivation, and methodology rationale where appropriate.
Ensure the response is in {lang_name}.
"""

# ==========================================
# Citation Intent Prompts
# ==========================================

CITATION_INTENT_PROMPT = """Identify and analyze all "citations" (references to other works) in the following academic text, and classify the intent of each citation.

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

# ==========================================
# Author Agent Prompts
# ==========================================

AUTHOR_PERSONA_PROMPT = """
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
# Claim Verification Prompts
# ==========================================

CLAIM_VERIFICATION_PROMPT = """You are an autonomous "Evidence Checker".
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
# Dictionary Prompts
# ==========================================

DICT_EXPLAIN_PROMPT = """Provide the translation of the English word "{word}" in {lang_name} and a concise explanation (approx. 15 characters or 3-5 words).
Format: [Translation] Explanation
"""

# ==========================================
# PDF Processing & OCR Prompts
# ==========================================

PDF_LANG_DETECT_PROMPT = """Identify the primary language of the following text and return ONLY the ISO 639-1 code (e.g., 'en', 'ja', 'fr').
Text Sample:
{text}
"""

PDF_FALLBACK_OCR_PROMPT = (
    "Transcribe the text from this PDF page preserving the structure as much as possible."
)
