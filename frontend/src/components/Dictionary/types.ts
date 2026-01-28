export interface DictionaryEntry {
    word: string;
    translation: string;
    source: string; // Cache, Jamdict, Gemini, Error
}

export interface ExplanationResponse {
    explanation: string;
}
