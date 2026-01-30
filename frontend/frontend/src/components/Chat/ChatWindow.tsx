import React, { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Message } from './types';
import MessageList from './MessageList';
import InputArea from './InputArea';

interface ChatWindowProps {
    sessionId?: string;
    paperId?: string | null;
    initialMessages?: Message[];
    initialFigureId?: string | null;
    onInitialChatSent?: () => void;
    initialPrompt?: string | null;
    onInitialPromptSent?: () => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ 
    sessionId = 'default', 
    paperId, 
    initialMessages = [],
    initialFigureId,
    onInitialChatSent,
    initialPrompt,
    onInitialPromptSent
}) => {
    const [messages, setMessages] = useState<Message[]>(initialMessages);
    const [isLoading, setIsLoading] = useState(false);

    // Load messages when paperId changes
    React.useEffect(() => {
        const fetchHistory = async () => {
            setMessages([]);
            
            // Initial messages prop might be useful, but usually we want server history if available
            // If paperId is not set, we might be in global context?
            
            setIsLoading(true);
            try {
                const url = new URL('/chat/history', window.location.origin);
                url.searchParams.append('session_id', sessionId);
                if (paperId) url.searchParams.append('paper_id', paperId);

                const res = await fetch(url.toString());
                if (res.ok) {
                    const data = await res.json();
                    if (data.history && Array.isArray(data.history)) {
                         const loadedMessages: Message[] = data.history.map((h: any) => ({
                             id: uuidv4(), // We generate ID as it's not persisted in simple history (role/content)
                             role: h.role,
                             content: h.content,
                             timestamp: Date.now()
                         }));
                         setMessages(loadedMessages);
                    }
                }
            } catch (e) {
                console.error("Failed to load chat history", e);
            } finally {
                setIsLoading(false);
            }
        };

        fetchHistory();
    }, [sessionId, paperId]);

    // Handle initial figure chat trigger
    React.useEffect(() => {
        if (initialFigureId && onInitialChatSent) {
            handleSendMessage("この図について詳しく教えてください。", initialFigureId);
            onInitialChatSent();
        }
    }, [initialFigureId, onInitialChatSent]);

    // Handle initial prompt chat trigger
    React.useEffect(() => {
        if (initialPrompt && onInitialPromptSent) {
            handleSendMessage(initialPrompt);
            onInitialPromptSent();
        }
    }, [initialPrompt, onInitialPromptSent]);

    const handleSendMessage = async (text: string, figureId?: string) => {
        // Add user message immediately
        const userMsg: Message = {
            id: uuidv4(),
            role: 'user',
            content: text,
            timestamp: Date.now(),
        };

        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId,
                    paper_id: paperId,
                    figure_id: figureId,
                    author_mode: false,
                    lang: 'ja', // Defaulting to Japanese as per project goals
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to send message');
            }

            const data = await response.json();

            const aiMsg: Message = {
                id: uuidv4(),
                role: 'assistant',
                content: data.response,
                timestamp: Date.now(),
            };

            setMessages(prev => [...prev, aiMsg]);
        } catch (error) {
            console.error('Chat error:', error);
            // Determine error message based on error type? For now generic.
            const errorMsg: Message = {
                id: uuidv4(),
                role: 'assistant',
                content: 'エラーが発生しました。もう一度お試しください。',
                timestamp: Date.now(),
            };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full w-full bg-white border-l border-gray-200">
            <div className="bg-white p-4 border-b border-gray-200 shadow-sm z-10">
                <h2 className="font-semibold text-gray-800 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 mr-2 text-blue-600">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                    </svg>
                    Chat Assistant
                </h2>
            </div>

            <MessageList messages={messages} isLoading={isLoading} />
            <InputArea onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>
    );
};

export default ChatWindow;
