import React, { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar/Sidebar'
import PDFViewer from './components/PDF/PDFViewer'
import { useAuth } from './contexts/AuthContext'
import Login from './components/Auth/Login'

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
    const [jumpTarget, setJumpTarget] = useState<{ page: number, x: number, y: number } | null>(null)
    const [showLoginModal, setShowLoginModal] = useState(false)
    const [currentPaperId, setCurrentPaperId] = useState<string | null>(null)
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [pendingFigureId, setPendingFigureId] = useState<string | null>(null)
    const [pendingChatPrompt, setPendingChatPrompt] = useState<string | null>(null)
    const [sidebarWidth, setSidebarWidth] = useState(384)
    const [isResizing, setIsResizing] = useState(false)
    const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)

    const prevPaperIdRef = useRef<string | null>(null);

    // Developer settings
    const SHOW_DEV_TOOLS = true;

    useEffect(() => {
        if (user) {
            setShowLoginModal(false)
            fetch('/api/config')
                .then(res => res.json())
                .then(data => setConfig(data))
                .catch(err => console.error(err))
        }
    }, [user])

    // Context Cache Lifecycle Management
    useEffect(() => {
        const deleteCache = (paperId: string) => {
            const formData = new FormData();
            formData.append('session_id', sessionId);
            formData.append('paper_id', paperId);
            
            if (navigator.sendBeacon) {
                navigator.sendBeacon('/chat/cache/delete', formData);
            } else {
                fetch('/chat/cache/delete', {
                    method: 'POST',
                    body: formData,
                    keepalive: true
                }).catch(e => console.error('Failed to delete cache:', e));
            }
        };

        if (prevPaperIdRef.current && prevPaperIdRef.current !== currentPaperId) {
            deleteCache(prevPaperIdRef.current);
        }
        prevPaperIdRef.current = currentPaperId;
    }, [currentPaperId, sessionId]);

    useEffect(() => {
        const handleBeforeUnload = () => {
            if (currentPaperId) {
                const formData = new FormData();
                formData.append('session_id', sessionId);
                formData.append('paper_id', currentPaperId);
                navigator.sendBeacon('/chat/cache/delete', formData);
            }
        };


        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [currentPaperId, sessionId]);

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {

            if (!isResizing) return;
            // Calculate new width from right side
            const newWidth = window.innerWidth - e.clientX;
            // Constrain width between 200px and half the screen
            if (newWidth > 200 && newWidth < window.innerWidth * 0.7) {
                setSidebarWidth(newWidth);
            }
        };

        const handleMouseUp = () => {
            setIsResizing(false);
            document.body.style.cursor = 'default';
            document.body.style.userSelect = 'auto';
        };

        if (isResizing) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        }

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isResizing]);

    const handlePaperLoaded = (paperId: string | null) => {
        setCurrentPaperId(paperId);
    }
    
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setUploadFile(e.target.files[0])
            setCurrentPaperId(null);
            // Reset all paper-specific states
            setSelectedWord(undefined);
            setSelectedContext(undefined);
            setSelectedCoordinates(undefined);
            setSelectedImage(undefined);
            setPendingChatPrompt(null);
            setPendingFigureId(null);
            setActiveTab('chat');
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



    const handleAskAI = (prompt: string) => {
        setPendingChatPrompt(prompt);
        setActiveTab('chat');
    }

    return (
        <div className="flex h-screen w-full bg-gray-100 overflow-hidden">
            {/* Sidebar Placeholder */}
            <div className={`bg-gray-900 text-white transition-all duration-300 ease-in-out hidden md:flex flex-col shrink-0 ${isLeftSidebarOpen ? 'w-64 opacity-100' : 'w-0 opacity-0 overflow-hidden'}`}>
                <div className="w-64 p-4 flex flex-col h-full">
                    <h1 className="text-xl font-bold mb-8">PaperTerrace</h1>
                <div className="flex-1">
                    <p className="text-gray-400 text-sm">Validating React Migration...</p>
                    {config && <p className="text-green-400 text-xs mt-2">● API Connected</p>}
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

                    {SHOW_DEV_TOOLS && (
                        <div className="mt-4 pt-4 border-t border-gray-700">
                            <button
                                onClick={() => {
                                    fetch('/test.pdf')
                                        .then(res => res.blob())
                                        .then(blob => {
                                            const file = new File([blob], "test.pdf", { type: "application/pdf" });
                                            setUploadFile(file);
                                            setCurrentPaperId(null);
                                        })
                                        .catch(e => console.error("Failed to load test PDF:", e));
                                }}
                                id="dev-load-pdf-btn"
                                className="w-full py-1 px-3 bg-indigo-900/50 hover:bg-indigo-900 text-indigo-200 text-xs rounded border border-indigo-800 transition-colors"
                            >
                                [DEV] Load Test.pdf
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col h-full relative transition-all duration-300">
                <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 shadow-sm">
                    <button
                        onClick={() => setIsLeftSidebarOpen(!isLeftSidebarOpen)}
                        className="mr-3 p-1.5 hover:bg-slate-100 rounded-lg transition-colors text-slate-500"
                        title={isLeftSidebarOpen ? "メニューを閉じる" : "メニューを開く"}
                    >
                        {isLeftSidebarOpen ? (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                            </svg>
                        )}
                    </button>
                    <span className="font-semibold text-gray-700">Reading Mode</span>
                    <div className="flex-1" />
                    {uploadFile && <span className="text-sm text-gray-500">{uploadFile.name}</span>}
                </header>

                <div className="flex-1 flex overflow-hidden">
                    {/* PDF Viewer Area */}
                    <div className="flex-1 bg-slate-100 flex items-start justify-center relative overflow-hidden">
                        {uploadFile ? (
                            <div className="w-full h-full p-4 md:p-8 overflow-y-auto custom-scrollbar">
                                <PDFViewer
                                    sessionId={sessionId}
                                    uploadFile={uploadFile}
                                    onWordClick={handleWordClick}
                                    onTextSelect={handleTextSelect}
                                    onAreaSelect={handleAreaSelect}
                                    jumpTarget={jumpTarget}
                                    onStatusChange={handleAnalysisStatusChange}
                                    onPaperLoaded={handlePaperLoaded}
                                    onAskAI={handleAskAI}
                                />
                            </div>
                        ) : (
                            <div className="bg-white p-8 rounded shadow text-center text-gray-400">
                                Select a PDF to view
                            </div>
                        )}
                    </div>

                    {/* Resizer Handle */}
                    <div
                        className={`w-1.5 h-full cursor-col-resize hover:bg-indigo-500/30 transition-colors z-30 shrink-0 ${isResizing ? 'bg-indigo-500/50' : 'bg-transparent'}`}
                        onMouseDown={(e) => {
                            e.preventDefault();
                            setIsResizing(true);
                        }}
                    >
                        <div className="w-[1px] h-full bg-gray-200 mx-auto" />
                    </div>

                    {/* Right Sidebar */}
                    <div 
                        style={{ width: sidebarWidth }}
                        className="h-full shadow-xl z-20 bg-white overflow-hidden shrink-0"
                    >
                        <Sidebar
                            sessionId={sessionId}
                            activeTab={activeTab}
                            onTabChange={setActiveTab}
                            selectedWord={selectedWord}
                            context={selectedContext}
                            coordinates={selectedCoordinates}
                            selectedImage={selectedImage}
                            onJump={handleJumpToLocation}
                            isAnalyzing={isAnalyzing}
                            paperId={currentPaperId}
                            pendingFigureId={pendingFigureId}
                            onPendingFigureConsumed={() => setPendingFigureId(null)}
                            pendingChatPrompt={pendingChatPrompt}
                            onAskAI={handleAskAI}
                            onPendingChatConsumed={() => setPendingChatPrompt(null)}
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
