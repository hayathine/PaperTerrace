export interface GroundingSupport {
	segment_text?: string;
	content?: string;
}

export interface GroundingChunk {
	content?: string;
}

export interface Grounding {
	supports?: GroundingSupport[];
	chunks?: GroundingChunk[];
}

export interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	timestamp: number;
	grounding?: Grounding;
	traceId?: string;
}

export interface ChatResponse {
	response: string;
	grounding?: Grounding;
}
