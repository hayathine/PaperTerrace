import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar/Sidebar'
import PDFViewer from './components/PDF/PDFViewer'
import { useAuth } from './contexts/AuthContext'
import Login from './components/Auth/Login'
import PaperList from './components/Library/PaperList'
import { PageData } from './components/PDF/types'
import UploadZone from './components/PDF/UploadZone'

function App() {
    const { user, logout } = useAuth()
    const [config, setConfig] = useState<any>(null)
    const [uploadFile, setUploadFile] = useState<File | null>(null)

    // Sidebar State
    const [sessionId] = useState(() => {
        const saved = localStorage.getItem('paper_terrace_session');
        if (saved) return saved;
        const newId = `session-${Math.random().toString(36).substring(2, 11)}`;
        localStorage.setItem('paper_terrace_session', newId);
        return newId;
    })
    const [activeTab, setActiveTab] = useState('chat')
    const [selectedWord, setSelectedWord] = useState<string | undefined>(undefined)
    const [selectedContext, setSelectedContext] = useState<string | undefined>(undefined)
    const [selectedCoordinates, setSelectedCoordinates] = useState<{ page: number, x: number, y: number } | undefined>(undefined)
    const [selectedImage, setSelectedImage] = useState<string | undefined>(undefined)
    const [jumpTarget, setJumpTarget] = useState<{ page: number, x: number, y: number, term?: string } | null>(null)
    const [evidenceHighlight, setEvidenceHighlight] = useState<{ page: number, text: string } | null>(null);
    const [initialChatMessage, setInitialChatMessage] = useState<string | null>(null);

    const handleEvidenceClick = (evidence: { page: number, text: string }) => {
        setEvidenceHighlight(evidence);
        // Also jump to that page. For now just scroll to the top of that page.
        // We'll set x,y to -1 as a special value to indicate "just jump to page" 
        // OR we can try to find the coordinates if we have the index.
        setJumpTarget({ page: evidence.page, x: 0.5, y: 0.2 }); // Jump to top-middle of that page
    }
    const [showLoginModal, setShowLoginModal] = useState(false)
    const [currentPaperId, setCurrentPaperId] = useState<string | null>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [initialPages, setInitialPages] = useState<PageData[] | undefined>(undefined)

    const handleSelectPaper = async (paperId: string) => {
        setCurrentPaperId(paperId);
        setIsAnalyzing(true);
        setInitialPages(undefined);

        try {
            const headers: HeadersInit = {};
            // if (token) headers['Authorization'] = `Bearer ${token}`; // Need to get token here if used

            const res = await fetch(`/papers/${paperId}`, { headers });
            if (res.ok) {
                const data = await res.json();
                if (data.layout_json) {
                    try {
                        const layout = JSON.parse(data.layout_json);
                        // Convert DB layout to PageData format
                        const pages: PageData[] = layout.map((lp: any, idx: number) => ({
                            page_num: idx + 1,
                            image_url: `/static/paper_images/${data.file_hash}/page_${idx + 1}.png`,
                            width: lp?.width || 0,
                            height: lp?.height || 0,
                            words: lp?.words || [],
                            figures: lp?.figures || []
                        }));
                        setInitialPages(pages);
                    } catch (e) {
                        console.error('Failed to parse layout_json', e);
                    }
                }
            }
        } catch (e) {
            console.error('Failed to load paper', e);
        } finally {
            setIsAnalyzing(false);
        }
    }

    useEffect(() => {
        const path = window.location.pathname;
        const match = path.match(/^\/(?:papers|reader|pdf)\/([a-z0-9-]+)/i);
        if (match && match[1]) {
            handleSelectPaper(match[1]);
        }
    }, [])

    useEffect(() => {
        if (user) {
            setShowLoginModal(false)
            fetch('/api/config')
                .then(res => res.json())
                .then(data => setConfig(data))
                .catch(err => console.error(err))
        }
    }, [user])

    const handlePaperLoaded = (paperId: string | null) => {
        setCurrentPaperId(paperId);
    }
    
    const handleAskAI = (prompt: string) => {
        setInitialChatMessage(prompt);
        setActiveTab('Chat');
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setUploadFile(e.target.files[0])
            setCurrentPaperId(null);
        }
    }


    const handleWordClick = (word: string, context?: string, coords?: { page: number, x: number, y: number }) => {
        setSelectedWord(word)
        setSelectedContext(context)
        setSelectedCoordinates(coords)
        setActiveTab('dict')
    }

    const handleTextSelect = (text: string, coords: { page: number, x: number, y: number }) => {
        // When text is selected, we want to maybe open notes?
        // Let's set selected context as the text
        setSelectedWord(undefined)
        setSelectedContext(text)
        setSelectedImage(undefined) // Clear image
        setSelectedCoordinates(coords)
        setActiveTab('notes') // Switch to notes for saving selection
    }

    const handleAreaSelect = (imageUrl: string, coords: { page: number, x: number, y: number }) => {
        setSelectedWord(undefined)
        setSelectedContext(undefined)
        setSelectedImage(imageUrl)
        setSelectedCoordinates(coords)
        setActiveTab('notes')
    }

    const handleJumpToLocation = (page: number, x: number, y: number) => {
        setJumpTarget({ page, x, y })
    }

    const handleAnalysisStatusChange = (status: string) => {
        setIsAnalyzing(status === 'uploading' || status === 'processing');
    }

    return (
        <div className="flex h-screen w-full bg-gray-100 overflow-hidden">
            {/* Sidebar Placeholder */}
            <div className="w-72 bg-gray-900 text-white p-4 hidden md:flex flex-col border-r border-gray-800">
                <div className="flex items-center gap-3 mb-10 px-2">
                    <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <span className="text-2xl font-black italic text-white">T</span>
                    </div>
                    <div>
                        <h1 className="text-xl font-black tracking-tighter text-white">Paper<span className="text-indigo-400">Terrace</span></h1>
                        <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest leading-none">Intelligence Hub</p>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    <PaperList onSelectPaper={handleSelectPaper} currentPaperId={currentPaperId} />
                    {config && (
                        <div className="px-4 py-2 mt-4">
                            <div className="flex items-center gap-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">System Online</span>
                            </div>
                        </div>
                    )}
                </div>

                <div className="mt-auto mb-4">
                    {user && (
                        <div className="flex items-center gap-2 mb-4 p-2 bg-gray-800 rounded">
                            {user.photoURL ? <img src={user.photoURL} alt="User" className="w-8 h-8 rounded-full" /> : <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold">{user.displayName?.[0] || 'U'}</div>}
                            <div className="overflow-hidden">
                                <p className="text-sm font-medium truncate">{user.displayName || 'User'}</p>
                                <p className="text-xs text-gray-400 truncate">{user.email || ''}</p>
                            </div>
                        </div>
                    )}
                    {!user && (
                        <div className="flex items-center gap-2 mb-4 p-2 bg-gray-800 rounded">
                            <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-xs font-bold">G</div>
                            <div className="overflow-hidden">
                                <p className="text-sm font-medium truncate">Guest User</p>
                                <p className="text-xs text-gray-400 truncate">Limited Access</p>
                            </div>
                        </div>
                    )}
                    {user ? (
                        <button
                            onClick={logout}
                            className="w-full py-2 px-4 bg-red-600 hover:bg-red-700 rounded text-sm transition-colors"
                        >
                            Sign Out
                        </button>
                    ) : (
                        <button
                            onClick={() => setShowLoginModal(true)}
                            className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 rounded text-sm transition-colors"
                        >
                            Sign In / Sign Up
                        </button>
                    )}
                </div>

                <div className="mt-4">
                    <label className="block text-xs font-bold mb-2 text-gray-400">UPLOAD PDF</label>
                    <input
                        type="file"
                        accept="application/pdf"
                        onChange={handleFileChange}
                        className="block w-full text-sm text-gray-400
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-gray-700 file:text-white
                  hover:file:bg-gray-600
                  cursor-pointer
                "
                    />
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col h-full relative">
                <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 shadow-sm justify-between">
                    <span className="font-semibold text-gray-700">Reading Mode</span>
                    {uploadFile && <span className="text-sm text-gray-500">{uploadFile.name}</span>}
                </header>

                <div className="flex-1 flex overflow-hidden">
                    {/* PDF Viewer Area */}
                    <div className="flex-1 bg-slate-100 flex items-center justify-center relative overflow-hidden">
                        {uploadFile || initialPages ? (
                            <div className="w-full h-full p-4 md:p-8 overflow-y-auto custom-scrollbar">
                                <PDFViewer
                                    sessionId={sessionId}
                                    uploadFile={uploadFile}
                                    initialData={initialPages}
                                    onWordClick={handleWordClick}
                                    onTextSelect={handleTextSelect}
                                    onAreaSelect={handleAreaSelect}
                                    jumpTarget={jumpTarget}
                                    evidenceHighlight={evidenceHighlight}
                                    onStatusChange={handleAnalysisStatusChange}
                                    onPaperLoaded={handlePaperLoaded}
                                    onAskAI={handleAskAI}
                                />
                            </div>
                        ) : (
                            <UploadZone onFileChange={(file: File) => {
                                setUploadFile(file);
                                setCurrentPaperId(null);
                            }} />
                        )}
                    </div>

                    {/* Right Sidebar */}
                    <div className="w-96 h-full shadow-xl z-20 border-l border-gray-200 bg-white">
                        <Sidebar
                            sessionId={sessionId}
                            activeTab={activeTab}
                            onTabChange={setActiveTab}
                            selectedWord={selectedWord}
                            context={selectedContext}
                            coordinates={selectedCoordinates}
                            selectedImage={selectedImage}
                            onJump={handleJumpToLocation}
                            onEvidenceClick={handleEvidenceClick}
                            isAnalyzing={isAnalyzing}
                            initialChatMessage={initialChatMessage}
                            onClearInitialChatMessage={() => setInitialChatMessage(null)}
                        />
                    </div>
                </div>
            </div>

            {/* Login Modal */}
            {showLoginModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
                    <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
                        <button
                            onClick={() => setShowLoginModal(false)}
                            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
                        >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                        <Login onGuestAccess={() => setShowLoginModal(false)} />
                    </div>
                </div>
            )}
        </div>
    )
}

export default App
