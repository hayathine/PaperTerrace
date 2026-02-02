export interface SummaryResponse {
  summary?: string;
  sections?: Record<string, string>;
  abstract?: string;
  error?: string;
  // Integrated fields
  overview?: string;
  key_contributions?: SummarySection[];
  methodology?: SummarySection;
  conclusion?: SummarySection;
  all_detected_items?: VisualElement[];
}

export interface SummarySection {
  content: string;
  evidence_labels: string[];
}

export interface VisualElement {
  label: string;
  type: string;
  page_num: number;
  box_2d: number[];
  description?: string;
}

export interface HiddenAssumption {
  assumption: string;
  risk: string;
  severity: string;
}

export interface UnverifiedCondition {
  condition: string;
  impact: string;
  severity: string;
}

export interface ReproducibilityRisk {
  risk: string;
  detail: string;
  severity: string;
}

export interface MethodologyConcern {
  concern: string;
  suggestion: string;
  severity: string;
}

export interface CritiqueResponse {
  overall_assessment?: string;
  hidden_assumptions?: HiddenAssumption[];
  unverified_conditions?: UnverifiedCondition[];
  reproducibility_risks?: ReproducibilityRisk[];
  methodology_concerns?: MethodologyConcern[];
  error?: string;
}

export interface RelatedPaper {
  title: string;
  authors?: string[];
  year?: number;
  abstract?: string;
  url?: string;
}

export interface RadarResponse {
  related_papers?: RelatedPaper[];
  search_queries?: string[];
  error?: string;
}
