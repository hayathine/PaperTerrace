export interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	timestamp: number;
	grounding?: any;
	traceId?: string;
}

export interface ChatResponse {
	response: string;
	grounding?: any;
}
