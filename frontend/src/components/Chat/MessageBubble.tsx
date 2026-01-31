import React from 'react';
import { Message } from './types';

interface MessageBubbleProps {
    message: Message;
    onStackPaper?: (url: string, title?: string) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onStackPaper }) => {
    const isUser = message.role === 'user';

    const renderContent = (content: string) => {
        // Regex that matches URLs, allowing them to continue across a single newline
        // if the next line starts immediately with non-whitespace characters.
        const urlRegex = /(https?:\/\/(?:[^\s\n]|\n(?!\n)\S)+)/g;
        const parts = content.split(urlRegex);
        
        return parts.map((part, i) => {
            if (part.match(/^https?:\/\//)) {
                // Remove newlines for the actual URL to be used in links and stacking
                const healedUrl = part.replace(/\n+/g, '').trim();
                return (
                    <button
                        key={i}
                        onClick={(e) => {
                            e.preventDefault();
                            if (onStackPaper) {
                                onStackPaper(healedUrl);
                            }
                            // Also open the link in a new tab
                            window.open(healedUrl, '_blank', 'noopener,noreferrer');
                        }}
                        className="text-blue-500 hover:text-blue-700 underline break-all inline-flex items-center gap-1 group/link text-left"
                        title="Stack this paper"
                    >
                        {part}
                        <svg className="w-3 h-3 min-w-[12px] opacity-0 group-hover/link:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                    </button>
                );
            }
            return part;
        });
    };

    return (
        <div className={`flex w-full mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`max-w-[80%] rounded-lg px-4 py-2 shadow-sm ${isUser
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
                    }`}
            >
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {renderContent(message.content)}
                </div>
                <span className={`text-xs block mt-1 ${isUser ? 'text-blue-100' : 'text-gray-400'}`}>
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
            </div>
        </div>
    );
};

export default MessageBubble;
