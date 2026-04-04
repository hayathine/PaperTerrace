"""
DSPy Signature 用シードプロンプト（変数なし）

GEPAが __doc__ として最適化するための初期指示文を定義します。
実際のデータ（paper_text, lang_name 等）は InputField/OutputField で渡すため、
このファイルには含みません。
"""

# ==========================================
# System Layer
# ==========================================

SYSTEM_CONTEXT_SEED = """You are an expert academic research assistant (PaperTerrace).
Define the global behavioral constraints for the current task and output language.
Output must be invariant across users — do not reference user-specific data.
Cover: assistant role, language enforcement, output quality standards, and domain focus."""

# ==========================================
# Persona Adapter
# ==========================================

PERSONA_ADAPTER_SEED = """Generate behavioral instructions for the assistant based on the user's persona.
These instructions control tone, terminology level, and explanation depth.
Must stay consistent with the provided system_context constraints.
Do NOT reference any specific content — output pure behavioral policy only."""

# ==========================================
# Summary
# ==========================================

PAPER_SUMMARY_SEED = """Summarize the academic paper into structured sections.
Respond entirely in the language specified by `lang_name`.
Keep the total output concise (aim for under 1000 tokens).

Output 5 sections:
1. Overview: 1-2 sentences summarizing the main theme
2. Key Contributions: 2-4 clear bullet points
3. Methodology: Concise explanation of methods used
4. Conclusion: Key findings and implications
5. Key Words: 5-10 technical keywords (MUST be in English)

All section headers and content (except Key Words) MUST be in the requested language."""

PAPER_SUMMARY_SECTIONS_SEED = """Summarize the academic paper section by section.
Respond entirely in the language specified by `lang_name`.
For each section, produce a concise summary of 2-3 sentences."""

# ==========================================
# Translation
# ==========================================

CONTEXT_AWARE_TRANSLATION_SEED = """Translate the target word or phrase using the surrounding academic paper context.
Respond entirely in the language specified by `lang_name`.
Prioritize domain-specific accuracy over literal translation.
If the term is a proper noun, acronym, or project name that should remain in English, use the original term as the translation.
Output ONLY the translated word or a concise translation with a brief context-aware explanation.
Do NOT include meta-comments like "(そのまま)" or "(As-is)" in your output.

Examples(Japanese):
- Context: correlation between variables. Target: significant → 有意な 
- Context: outperforms SOTA models. Target: SOTA → 最先端の 
- Context: Large Language Models (LLMs). Target: LLMs → 大規模言語モデル """

SIMPLE_TRANSLATION_SEED = """Translate the target word or phrase concisely based on the academic context.
Respond entirely in the language specified by `lang_name`.
If the term is a proper noun or acronym, output the original term.
Output ONLY the translation (1-3 words).
Do NOT include meta-comments like "(そのまま)" or "(As-is)" in your output.

Examples(Japanese):
- Context: correlation between variables. Target: significant → 有意な 
- Context: outperforms SOTA models. Target: SOTA → 最先端の 
- Context: Large Language Models (LLMs). Target: LLMs → 大規模言語モデル """

DEEP_EXPLANATION_SEED = """Explain the target word or phrase in the context of the academic paper.
Respond entirely in the language specified by `lang_name`.
Do NOT just translate — focus on its specific meaning, role, or technical significance within this paper.
If it is a technical term, explain the underlying concept briefly.
If it refers to a methodology or result, explain its importance."""

# ==========================================
# Chat
# ==========================================

CHAT_GENERAL_SEED = """Answer the user's question about the academic paper.
Use the provided paper context and conversation history.
Provide a clear and concise answer in the language specified by `lang_name`."""

# ==========================================
# Agent / Review
# ==========================================

ADVERSARIAL_CRITIQUE_SEED = """Critically review the academic paper and identify potential issues.
Analyze from a rigorous reviewer's perspective.
Limit each category to a maximum of 3 most significant items.
Keep descriptions concise (total response under 1000 tokens).
Be constructive but critical."""

VISION_FIGURE_SEED = """Analyze the figure (graph, table, or diagram) from the academic paper.
Explain the following points:
1. Type & Overview: What the figure represents
2. Key Findings: Main trends or patterns observed
3. Interpretation: Meaning of the numbers or trends
4. Implications: How this supports the paper's claims
5. Highlights: Notable points or anomalies

Verbalize visual information so it can be understood without seeing the figure."""

# ==========================================
# Recommendation
# ==========================================

PAPER_RECOMMENDATION_SEED = """Recommend the next academic papers the user should read based on their knowledge level, interests, and unknown concepts.
- Provide at least 3 recommended papers with titles and reasons.
- Generate at least 2 search queries for Semantic Scholar.
- For beginner users, including survey papers is preferred."""

USER_PROFILE_ESTIMATION_SEED = """Estimate the user's understanding, interests, and unknown concepts from their behavioral data.
- Knowledge level: Beginner / Intermediate / Advanced
- Extract interesting topics
- Identify concepts the user might not understand
- Recommended direction: Deep dive / Broadening / Application / Fundamentals"""

# ==========================================
# Direct API Prompts (with template variables)
# ==========================================
# Gemini Vision API や Llamacpp など、DSPy を介さず直接 LLM に渡すプロンプト

CORE_SYSTEM_PROMPT = """You are an expert academic research assistant.
Your goal is to help users understand complex academic papers, translate technical terms accurately within context, and summarize research findings clearly.

# Global Rules
1. CRITICAL: Always output in the requested language (e.g., if asked for Japanese, answer in Japanese). However, maintain original notation for proper nouns, acronyms, and technical terms that are commonly used as-is in that language's academic community.
2. When translating, prioritize accuracy and academic context. For specific terms, provide both a translation (or original term if appropriate) and a brief context-aware explanation.
3. capture the core essence, methods, and contributions in summaries.
4. If the user asks for JSON, output ONLY valid JSON without Markdown formatting.
5. Do NOT add meta-comments like "(そのまま)" or "(Translation: ...)" to the output.
"""

# ------------------------------------------
# Fixed System Prompt for Translation (Prefix Caching optimized)
# ------------------------------------------

DICT_TRANSLATE_SYSTEM_PROMPT = """Translate using domain-accurate terminology.
If abbreviation, expand it like: "LLM → 大規模言語モデル".Output only the translation."""

DICT_TRANSLATE_LLM_PROMPT = """{paper_title}. Translate the word to {lang_name}.
Input: {target_word}
Translation:"""

DICT_TRANSLATE_LONG_SYSTEM_PROMPT = """Translate the following academic text accurately and naturally.
Maintain technical terminology, sentence structure, and meaning.
Output only the translation without any commentary."""

DICT_TRANSLATE_LONG_LLM_PROMPT = """Translate the following text to {lang_name}.
{context_line}
Input:
{target_text}

Translation:"""

TRANSLATE_FROM_PDF_PROMPT = """Translate the following term from the academic paper above.
Respond entirely in {lang_name}.
Prioritize domain-specific accuracy over literal translation.
If the term is a proper noun, acronym, or project name that should remain in English, use the original term.
Output ONLY the translation or a concise translation with a brief context-aware explanation.
Do NOT include meta-comments like "(そのまま)" or "(As-is)".
{context_line}
Term: {target_word}
Translation:"""

EXPLAIN_FROM_PDF_PROMPT = """Explain the following term from the academic paper above.
Respond entirely in {lang_name}.
Do NOT just translate — focus on its specific meaning, role, or technical significance within this paper.
If it is a technical term, explain the underlying concept briefly.
If it refers to a methodology or result, explain its importance.
{context_line}
Term: {target_word}
Explanation:"""


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

PDF_EXTRACT_TEXT_OCR_PROMPT = """\
Extract all body text from this academic paper page image and format it as Markdown.

Rules:
- Use `#` / `##` / `###` for section headings and subheadings based on font size and position.
- Preserve paragraph breaks with a blank line between paragraphs.
- Preserve inline formatting: bold, italic, equations as-is.
- **Omit** figure captions, table captions, and footnotes entirely.
- **Omit** page numbers, headers, and footers.
- Do NOT add any commentary or explanation — output transcribed text only.
- If a line is clearly a continuation of the previous paragraph (e.g., hyphenated word at line break), join them.
"""

PDF_EXTRACT_TEXT_OCR_BATCH_PROMPT = """\
You will receive multiple page images from an academic paper.
Extract all body text from each page image and format it as Markdown.

Rules:
- Use `#` / `##` / `###` for section headings and subheadings based on font size and position.
- Preserve paragraph breaks with a blank line between paragraphs.
- Preserve inline formatting: bold, italic, equations as-is.
- **Omit** figure captions, table captions, and footnotes entirely.
- **Omit** page numbers, headers, and footers.
- Do NOT add any commentary or explanation — output transcribed text only.
- If a line is clearly a continuation of the previous paragraph (e.g., hyphenated word at line break), join them.

IMPORTANT: Separate each page's output with the exact delimiter line: ===PAGE_N===
where N is the page number shown in the request (e.g., ===PAGE_3===).
Output ONLY the delimiters and extracted text — no other commentary.

Example output format:
===PAGE_1===
# Introduction
This paper presents...

===PAGE_2===
## Related Work
Prior work on...
"""
