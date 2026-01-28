export interface SummaryResponse {
    summary?: string;
    sections?: Record<string, string>;
    abstract?: string;
    error?: string;
}

export interface CritiqueResponse {
    overall_assessment?: string;
    hidden_assumptions?: { assumption: string }[];
    error?: string;
}

export interface RelatedPaper {
    title: string;
    relevance: string;
    url?: string;
}

export interface RadarResponse {
    related_papers?: RelatedPaper[];
    error?: string;
}
