import React from 'react';
import { Message } from './types';

interface MessageBubbleProps {
    message: Message;
    onEvidenceClick?: (evidence: any) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onEvidenceClick }) => {
    const isUser = message.role === 'user';

    const renderContent = () => {
        if (isUser || !message.evidence || message.evidence.length === 0) {
            return <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>;
        }

        // Parse citations like [1], [2], etc.
        const parts = message.content.split(/(\[\d+\])/g);
        return (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {parts.map((part, i) => {
                    const match = part.match(/\[(\d+)\]/);
                    if (match) {
                        const id = match[1];
                        const evidence = message.evidence?.find(e => e.id === id);
                        if (evidence) {
                            return (
                                <button
                                    key={i}
                                    onClick={() => onEvidenceClick?.(evidence)}
                                    className="inline-flex items-center justify-center w-5 h-5 mx-0.5 -mt-1 text-[10px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full hover:bg-indigo-600 hover:text-white transition-all shadow-sm"
                                    title={`Page ${evidence.page}: ${evidence.text.substring(0, 50)}...`}
                                >
                                    {id}
                                </button>
                            );
                        }
                    }
                    return part;
                })}
            </p>
        );
    };

    return (
        <div className={`flex w-full mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`max-w-[80%] rounded-lg px-4 py-2 shadow-sm ${isUser
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
                    }`}
            >
                {renderContent()}
                <span className={`text-xs block mt-1 ${isUser ? 'text-blue-100' : 'text-gray-400'}`}>
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
            </div>
        </div>
    );
};

export default MessageBubble;
