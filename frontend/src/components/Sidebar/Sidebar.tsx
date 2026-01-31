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
        <div className="flex flex-col h-full bg-white border-l border-slate-200 shadow-sm overflow-hidden font-sans">
            {/* Tab Navigation */}
            <div className="flex bg-slate-50 border-b border-slate-200 overflow-x-auto">
                <button
                    onClick={() => onTabChange('dict')}
                    className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${activeTab === 'dict'
                        ? 'bg-white text-indigo-600 border-indigo-600 shadow-none'
                        : 'text-slate-400 border-transparent hover:text-slate-600'
                        }`}
                >
                    Dict
                </button>
                <button
                    onClick={() => onTabChange('summary')}
                    className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${activeTab === 'summary'
                        ? 'bg-white text-indigo-600 border-indigo-600 shadow-none'
                        : 'text-slate-400 border-transparent hover:text-slate-600'
                        }`}
                >
                    Summary
                </button>

                <button
                    onClick={() => onTabChange('chat')}
                    className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${activeTab === 'chat'
                        ? 'bg-white text-indigo-600 border-indigo-600 shadow-none'
                        : 'text-slate-400 border-transparent hover:text-slate-600'
                        }`}
                >
                    Chat
                </button>
                <button
                    onClick={() => onTabChange('notes')}
                    className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${activeTab === 'notes'
                        ? 'bg-white text-indigo-600 border-indigo-600 shadow-none'
                        : 'text-slate-400 border-transparent hover:text-slate-600'
                        }`}
                >
                    Notes
                </button>
                <button
                    onClick={() => onTabChange('stack')}
                    className={`flex-1 min-w-[50px] py-3 text-[10px] font-bold uppercase tracking-[0.15em] transition-all border-b-2 ${activeTab === 'stack'
                        ? 'bg-white text-indigo-600 border-indigo-600 shadow-none'
                        : 'text-slate-400 border-transparent hover:text-slate-600'
                        }`}
                >
                    Stack
                </button>
            </div>

            {/* Tab Content - All rendered but hidden when not active to preserve state */}
            <div className="flex-1 overflow-hidden relative">
                <div className={`absolute inset-0 ${activeTab === 'dict' ? 'block' : 'hidden'}`}>
                    <Dictionary 
                        sessionId={sessionId} 
                        paperId={paperId} 
                        term={selectedWord} 
                        coordinates={coordinates}
                        onAskAI={onAskAI}
                        onJump={onJump}
                    />
                </div>
                
                <div className={`absolute inset-0 ${activeTab === 'summary' ? 'block' : 'hidden'}`}>
                    <Summary sessionId={sessionId} isAnalyzing={isAnalyzing} paperId={paperId} />
                </div>

                <div className={`absolute inset-0 ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
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

                <div className={`absolute inset-0 ${activeTab === 'notes' ? 'block' : 'hidden'}`}>
                    <NoteList
                        sessionId={sessionId}
                        paperId={paperId}
                        coordinates={coordinates}
                        onJump={onJump}
                        selectedContext={context}
                        selectedTerm={selectedWord}
                        selectedImage={selectedImage}
                    />
                </div>

                <div className={`absolute inset-0 ${activeTab === 'stack' ? 'block' : 'hidden'}`}>
                    <PaperStack 
                        papers={stackedPapers} 
                        onRemove={onRemoveFromStack} 
                    />
                </div>
            </div>
        </div>
    );
};

export default Sidebar;
