import React, { useState, useEffect, useCallback } from "react";
import ChatWindow from "../Chat/ChatWindow";
import NoteList from "../Notes/NoteList";
import Dictionary from "../Dictionary/Dictionary";
import Summary from "../Summary/Summary";
import { useAuth } from "../../contexts/AuthContext";

interface SidebarProps {
  sessionId: string;
  activeTab: string;
  onTabChange: (tab: string) => void;
  selectedWord?: string;
  context?: string;
  coordinates?: { page: number; x: number; y: number };
  selectedImage?: string;
  onJump?: (page: number, x: number, y: number) => void;
  isAnalyzing?: boolean;
  initialChatMessage?: string | null;
  onClearInitialChatMessage?: () => void;
  onEvidenceClick?: (evidence: any) => void;
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
  initialChatMessage,
  onClearInitialChatMessage,
  onEvidenceClick,
}) => {
  const { token } = useAuth();
  const [dictCount, setDictCount] = useState<number>(0);

  const fetchDictCount = useCallback(async () => {
    try {
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`/note/count/${sessionId}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setDictCount(data.count);
      }
    } catch (e) {
      console.error("Failed to fetch dict count", e);
    }
  }, [sessionId, token]);

  useEffect(() => {
    if (sessionId) {
      fetchDictCount();
    }
  }, [sessionId, fetchDictCount, activeTab]);

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200 shadow-xl overflow-hidden font-sans">
      {/* Tab Navigation */}
      <div className="flex p-2 bg-slate-50 border-b border-slate-100 overflow-x-auto gap-1">
        <button
          onClick={() => onTabChange("dict")}
          className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "dict"
              ? "bg-white text-indigo-600 shadow-sm border border-slate-100"
              : "text-slate-400 hover:text-slate-600"
          }`}
        >
          Dict
          {dictCount > 0 && (
            <span
              className={`px-1.5 py-0.5 rounded-full text-[8px] ${activeTab === "dict" ? "bg-indigo-100 text-indigo-600" : "bg-slate-100 text-slate-400"}`}
            >
              {dictCount}
            </span>
          )}
        </button>
        <button
          onClick={() => onTabChange("summary")}
          className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${
            activeTab === "summary"
              ? "bg-white text-indigo-600 shadow-sm border border-slate-100"
              : "text-slate-400 hover:text-slate-600"
          }`}
        >
          Summary
        </button>
        <button
          onClick={() => onTabChange("chat")}
          className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${
            activeTab === "chat"
              ? "bg-white text-indigo-600 shadow-sm border border-slate-100"
              : "text-slate-400 hover:text-slate-600"
          }`}
        >
          Chat
        </button>

        <button
          onClick={() => onTabChange("notes")}
          className={`flex-1 min-w-[50px] py-2 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${
            activeTab === "notes"
              ? "bg-white text-indigo-600 shadow-sm border border-slate-100"
              : "text-slate-400 hover:text-slate-600"
          }`}
        >
          Notes
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden relative">
        {activeTab === "dict" && (
          <div className="absolute inset-0">
            <Dictionary
              sessionId={sessionId}
              term={selectedWord}
              context={context}
              coordinates={coordinates}
              onSave={fetchDictCount}
            />
          </div>
        )}
        {activeTab === "summary" && (
          <div className="absolute inset-0">
            <Summary sessionId={sessionId} isAnalyzing={isAnalyzing} />
          </div>
        )}
        {activeTab === "chat" && (
          <div className="absolute inset-0">
            <ChatWindow
              sessionId={sessionId}
              initialPrompt={initialChatMessage}
              onPromptConsumed={onClearInitialChatMessage}
              onEvidenceClick={onEvidenceClick}
            />
          </div>
        )}

        {activeTab === "notes" && (
          <div className="absolute inset-0">
            <NoteList
              sessionId={sessionId}
              coordinates={coordinates}
              onJump={onJump}
              selectedContext={context} // Use the shared context prop which now also holds selected text
              selectedTerm={selectedWord} // Word click sets this
              selectedImage={selectedImage}
              onSave={fetchDictCount}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
