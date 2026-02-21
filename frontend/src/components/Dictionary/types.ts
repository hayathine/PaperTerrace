export interface DictionaryEntry {
	word: string;
	translation: string;
	source: string; // Cache, Local-LM, Gemini, Error
}

export interface ExplanationResponse {
	explanation: string;
}
