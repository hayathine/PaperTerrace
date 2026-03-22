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

Examples:
- Context: correlation between variables. Target: significant → 有意な (Japanese)
- Context: outperforms SOTA models. Target: SOTA → 最先端の (Japanese)
- Context: project name NAP4 is described. Target: NAP4 → NAP4 (Japanese)"""

SIMPLE_TRANSLATION_SEED = """Translate the target word or phrase concisely based on the academic context.
Respond entirely in the language specified by `lang_name`.
If the term is a proper noun or acronym, output the original term.
Output ONLY the translation (1-3 words).
Do NOT include meta-comments like "(そのまま)" or "(As-is)" in your output."""

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
