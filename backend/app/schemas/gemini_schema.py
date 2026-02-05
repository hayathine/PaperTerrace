from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --- Figure & Image Analysis ---


class FigureAnalysisResponse(BaseModel):
    """画像分析結果の構造化モデル"""

    type_overview: str = Field(..., description="図の概要と種類")
    key_findings: List[str] = Field(..., description="主な傾向やパターン")
    interpretation: str = Field(..., description="数値や傾向の解釈")
    implications: str = Field(..., description="論文の主張に対する裏付け")
    highlights: List[str] = Field(..., description="特筆すべき点や異常値")


class TableAnalysisResponse(BaseModel):
    """表分析結果の構造化モデル"""

    overview: str = Field(..., description="表の概要")
    key_numbers: List[str] = Field(..., description="重要な数値と傾向")
    comparisons: List[str] = Field(..., description="特筆すべき比較や差異")
    conclusions: str = Field(..., description="表から導かれる結論")


class FigureComparisonResponse(BaseModel):
    """図表比較結果の構造化モデル"""

    similarities: List[str] = Field(..., description="2つの図の類似点")
    differences: List[str] = Field(..., description="2つの図の相違点")
    relationship: str = Field(..., description="補完関係などの関連性")
    contradictions: Optional[List[str]] = Field(None, description="矛盾点（ある場合）")


class FigureBox(BaseModel):
    """Represents a bounding box for a detected figure, table, or equation."""

    label: str = Field(description="Type of item: figure, table, or equation")
    box_2d: List[float] = Field(description="[ymin, xmin, ymax, xmax] normalized coordinates 0-1")


class FigureDetectionResponse(BaseModel):
    """Response schema for figure detection."""

    figures: List[FigureBox] = Field(description="List of detected figures, tables, and equations")


class PageFigureBox(BaseModel):
    """Represents a bounding box for a detected item on a specific page."""

    page: int = Field(description="1-indexed page number")
    label: str = Field(description="Type of item: figure, table, or equation")
    box_2d: List[float] = Field(
        description="[ymin, xmin, ymax, xmax] normalized coordinates 0-1000"
    )


class WholePDFDetectionResponse(BaseModel):
    """Response schema for figure detection across an entire PDF."""

    items: List[PageFigureBox] = Field(description="List of detected items across all pages")


class BboxResponse(BaseModel):
    label: str
    bbox: List[float]
    polygon: List[List[float]]
    confidence: float = 1.0


# --- Math & Equations ---


class EquationAnalysisResponse(BaseModel):
    is_equation: bool
    confidence: float
    latex: str
    explanation: str


# --- Research & Search ---


class SimulatedPaper(BaseModel):
    title: str
    authors: List[str]
    year: int
    abstract: str
    url: str


class SimulatedSearchResponse(BaseModel):
    papers: List[SimulatedPaper]


class SearchQueriesResponse(BaseModel):
    """検索クエリ生成モデル"""

    queries: List[str] = Field(..., description="検索クエリリスト（3-5件）")


# --- Citations & Claims ---


class CitationIntent(BaseModel):
    """段落内の個別の引用の分析結果"""

    citation: str = Field(..., description="The citation string as it appears in the text")
    intent: str = Field(
        ...,
        description="Support | Use | Contrast | Criticize | Neutral",
    )
    reason: str = Field(..., description="1-sentence reason for classification in target language")


class CitationAnalysisResponse(BaseModel):
    """引用意図分析の全体レスポンス"""

    citations: List[CitationIntent]


class ClaimVerificationResponse(BaseModel):
    """結果報告のための構造化データモデル"""

    status: str = Field(..., description="warning | verified | neutral")
    summary: str = Field(
        ..., description="Short summary of the verification result (max 100 chars)."
    )
    details: str = Field(
        ...,
        description="Detailed report citing sources found during search. Mention if reproducible or accepted, or highlight doubts.",
    )
    sources: List[str] = Field(
        default_factory=list, description="List of URL or source names found"
    )


# --- Critical Thinking & Adversarial ---


class HiddenAssumption(BaseModel):
    assumption: str
    risk: str
    severity: Literal["high", "medium", "low"]


class UnverifiedCondition(BaseModel):
    condition: str
    impact: str
    severity: Literal["high", "medium", "low"]


class ReproducibilityRisk(BaseModel):
    risk: str
    detail: str
    severity: Literal["high", "medium", "low"]


class MethodologyConcern(BaseModel):
    concern: str
    suggestion: str
    severity: Literal["high", "medium", "low"]


class AdversarialCritiqueResponse(BaseModel):
    """Structured response for adversarial critique of a paper."""

    hidden_assumptions: List[HiddenAssumption]
    unverified_conditions: List[UnverifiedCondition]
    reproducibility_risks: List[ReproducibilityRisk]
    methodology_concerns: List[MethodologyConcern]
    overall_assessment: str


# --- Text Analysis & Summarization ---


class ParagraphExplanationResponse(BaseModel):
    """Paragraph explanation result model."""

    main_claim: str = Field(..., description="The core argument or content of this paragraph")
    background_knowledge: str = Field(
        ..., description="Prerequisites or technical terms needed to understand this"
    )
    logic_flow: str = Field(..., description="How the argument or logic is developed")
    key_points: List[str] = Field(..., description="Important implications or things to note")


class TermExplanation(BaseModel):
    """Technical term explanation model."""

    term: str = Field(..., description="The technical term")
    explanation: str = Field(..., description="Concise explanation of the term")
    importance: Literal["high", "medium", "low"] = Field(..., description="Importance level")


class TerminologyList(BaseModel):
    """List of technical terms with explanations."""

    terms: List[TermExplanation] = Field(
        ..., description="List of extracted technical terms", max_length=10
    )


class SectionSummary(BaseModel):
    """Represents a summary for a specific section of the paper."""

    section: str = Field(description="Title of the section")
    summary: str = Field(description="Summary of the section content")


class SectionSummaryList(BaseModel):
    """List of section summaries."""

    sections: List[SectionSummary] = Field(description="List of section summaries")


class FullSummaryResponse(BaseModel):
    """Paper full summary model."""

    overview: str = Field(..., description="Abstract or overview of the main theme (1-2 sentences)")
    key_contributions: List[str] = Field(..., description="List of 3-5 key contributions")
    methodology: str = Field(..., description="Concise explanation of the methodology")
    conclusion: str = Field(..., description="Key findings and implications")


# --- Integrated Analysis (Grounding) ---


class VisualElement(BaseModel):
    """Represents a visual item (figure, table, equation) with coordinates."""

    label: str = Field(..., description="Identifier like 'Figure 1', 'Table 2', or 'Eq. (5)'")
    type: str = Field(..., description="'figure', 'table', or 'equation'")
    page_num: int = Field(..., description="1-indexed page number")
    # Gemini's normalized [ymin, xmin, ymax, xmax] (0-1000)
    box_2d: List[int] = Field(..., description="Normalized bounding box [ymin, xmin, ymax, xmax]")
    description: Optional[str] = Field(None, description="Brief context of the element")


class SummarySection(BaseModel):
    """A section of the summary with links to visual evidence."""

    content: str = Field(..., description="The summary text in the target language")
    # Reference to labels in all_detected_items
    evidence_labels: List[str] = Field(
        default_factory=list,
        description="Labels of visual elements that support this summary point",
    )


class IntegratedAnalysisResponse(BaseModel):
    """The unified response containing structured summary and grounded coordinates."""

    overview: str = Field(..., description="A 1-2 sentence overview of the paper")
    key_contributions: List[SummarySection] = Field(
        ..., description="3-5 key contributions with visual grounding"
    )
    methodology: SummarySection = Field(
        ..., description="Technical explanation with visual grounding"
    )
    conclusion: SummarySection = Field(..., description="Main findings and implications")

    # Master list of all detected visual structures
    all_detected_items: List[VisualElement] = Field(
        ..., description="List of all figures, tables, and equations found"
    )
