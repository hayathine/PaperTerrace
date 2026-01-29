"""
Prompts configuration file.
Centralized location for all AI prompts used in PaperTerrace.
"""

# ==========================================
# Translation & Dictionary Prompts
# ==========================================

TRANSLATE_PHRASE_WITH_CONTEXT_PROMPT = """{paper_context}
以上の文脈を考慮して、以下の英文を{lang_name}に翻訳してください。

{original_word}

訳のみを出力してください。"""

TRANSLATE_WORD_SIMPLE_PROMPT = """{paper_context}
以上の論文の文脈において、英単語「{lemma}」はどのような意味ですか？
{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"""


TRANSLATE_WORD_WITH_CONTEXT_EXPLAIN_PROMPT = """
以下の文脈において、単語「{word}」はどういう意味で使われていますか？
文脈を考慮して、{lang_name}で簡潔に説明してください。

{summary_context}
文脈:
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
  {{"section": "Section Title", "summary": "Summary (2-3 sentences) in {lang_name}"}},
  ...
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

EXPLAIN_TERMINOLOGY_PROMPT = """Please extract technical terms from the paragraph below and provide concise explanations for each.

[Paragraph]
{paragraph}

{terms_hint}

Please output the explanations in {lang_name}.
Return the result strictly in the following JSON format:
[
  {{"term": "Term", "explanation": "Concise explanation (1-2 sentences) in {lang_name}", "importance": "high/medium/low"}}
]

Limit to at most 10 terms. Output JSON only.
"""
