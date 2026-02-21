export interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	timestamp: number;
}

export interface ChatResponse {
	response: string;
}
