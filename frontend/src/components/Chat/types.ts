export interface Evidence {
    id: string;
    page: number;
    text: string;
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    evidence?: Evidence[];
    timestamp: number;
}

export interface ChatResponse {
    response: string;
    evidence?: Evidence[];
}
