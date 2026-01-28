import React from 'react';
import ChatWindow from '../Chat/ChatWindow';
import NoteList from '../Notes/NoteList';
import Dictionary from '../Dictionary/Dictionary';
import Summary from '../Summary/Summary';
import FigureInsight from '../FigureInsight/FigureInsight';
import ParagraphExplain from '../ParagraphExplain/ParagraphExplain';

interface SidebarProps {
    sessionId: string;
    activeTab: string;
    onTabChange: (tab: string) => void;
    selectedWord?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ sessionId, activeTab, onTabChange, selectedWord }) => {

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
                    onClick={() => onTabChange('figure')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'figure'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Figure
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
                    onClick={() => onTabChange('explain')}
                    className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${activeTab === 'explain'
                        ? 'bg-white text-indigo-600 shadow-sm border border-slate-100'
                        : 'text-slate-400 hover:text-slate-600'
                        }`}
                >
                    Exp
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
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === 'dict' && (
                    <div className="absolute inset-0">
                        <Dictionary sessionId={sessionId} term={selectedWord} />
                    </div>
                )}
                {activeTab === 'summary' && (
                    <div className="absolute inset-0">
                        <Summary sessionId={sessionId} />
                    </div>
                )}
                {activeTab === 'figure' && (
                    <div className="absolute inset-0">
                        <FigureInsight sessionId={sessionId} />
                    </div>
                )}
                {activeTab === 'chat' && (
                    <div className="absolute inset-0">
                        <ChatWindow sessionId={sessionId} />
                    </div>
                )}
                {activeTab === 'explain' && (
                    <div className="absolute inset-0">
                        <ParagraphExplain sessionId={sessionId} />
                    </div>
                )}

                {activeTab === 'notes' && (
                    <div className="absolute inset-0">
                        <NoteList sessionId={sessionId} />
                    </div>
                )}
            </div>
        </div>
    );
};

export default Sidebar;
