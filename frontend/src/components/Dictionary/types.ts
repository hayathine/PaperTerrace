export interface DictionaryEntry {
	word: string;
	lemma?: string;
	translation: string;
	source: string; // Cache, Local-LM, Gemini, Error
	trace_id?: string;
}

export interface ExplanationResponse {
	explanation: string;
}
