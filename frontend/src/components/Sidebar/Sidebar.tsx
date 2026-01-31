import React from 'react';
import ChatWindow from '../Chat/ChatWindow';
import NoteList from '../Notes/NoteList';
import Dictionary from '../Dictionary/Dictionary';
import Summary from '../Summary/Summary';
import PaperStack from './PaperStack';

interface SidebarProps {
    sessionId: string;
    activeTab: string;
    onTabChange: (tab: string) => void;
    selectedWord?: string;
    context?: string;
    coordinates?: { page: number, x: number, y: number };
    selectedImage?: string;
    onJump?: (page: number, x: number, y: number, term?: string) => void;
    isAnalyzing?: boolean;
    paperId?: string | null;
    pendingFigureId?: string | null;
    onPendingFigureConsumed?: () => void;
    pendingChatPrompt?: string | null;
    onAskAI?: (prompt: string) => void;
    onPendingChatConsumed?: () => void;
    stackedPapers: { url: string, title?: string, addedAt: number }[];
    onStackPaper: (url: string, title?: string) => void;
    onRemoveFromStack: (url: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ 
    sessionId, 
    activeTab, 
    onTabChange, 
    selectedWord, 
    context, 
    coordinates, 
    selectedImage, 
    onJump, 
    isAnalyzing = false, 
    paperId,
    pendingFigureId,
    onPendingFigureConsumed,
    pendingChatPrompt,
    onAskAI,
    onPendingChatConsumed,
    stackedPapers,
    onStackPaper,
    onRemoveFromStack
}) => {

    return (
        <div className="flex flex-col h-full bg-white border-l border-gray-200 shadow-xl overflow-hidden font-sans">
            {/* Tab Navigation */}
            <div className="flex p-2 bg-slate-50 border-b border-slate-100 overflow-x-auto gap-1">
                <button
                    onClick={() => onTabChange('dict')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'dict'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Dict
                </button>
                <button
                    onClick={() => onTabChange('summary')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'summary'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Summary
                </button>

                <button
                    onClick={() => onTabChange('chat')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'chat'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Chat
                </button>
                <button
                    onClick={() => onTabChange('notes')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'notes'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Notes
                </button>
                <button
                    onClick={() => onTabChange('stack')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'stack'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Stack
                </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === 'dict' && (
                    <div className="absolute inset-0">
                        <Dictionary 
                            sessionId={sessionId} 
                            paperId={paperId} 
                            term={selectedWord} 
                            coordinates={coordinates}
                            onAskAI={onAskAI}
                            onJump={onJump}
                        />
                    </div>
                )}
                {activeTab === 'summary' && (
                    <div className="absolute inset-0">
                        <Summary sessionId={sessionId} isAnalyzing={isAnalyzing} paperId={paperId} />
                    </div>
                )}

                {activeTab === 'chat' && (
                    <div className="absolute inset-0">
                        <ChatWindow 
                            sessionId={sessionId} 
                            paperId={paperId} 
                            initialFigureId={pendingFigureId}
                            onInitialChatSent={onPendingFigureConsumed}
                            initialPrompt={pendingChatPrompt}
                            onInitialPromptSent={onPendingChatConsumed}
                            onStackPaper={onStackPaper}
                        />
                    </div>
                )}

                {activeTab === 'notes' && (
                    <div className="absolute inset-0">
                        <NoteList
                            sessionId={sessionId}
                            paperId={paperId}
                            coordinates={coordinates}
                            onJump={onJump}
                            selectedContext={context} // Use the shared context prop which now also holds selected text
                            selectedTerm={selectedWord} // Word click sets this
                            selectedImage={selectedImage}
                        />
                    </div>
                )}

                {activeTab === 'stack' && (
                    <div className="absolute inset-0">
                        <PaperStack 
                            papers={stackedPapers} 
                            onRemove={onRemoveFromStack} 
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default Sidebar;
