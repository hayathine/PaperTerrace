import React, { useState, useEffect } from 'react'
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
    const [isAnalyzing, setIsAnalyzing] = useState(false)

    useEffect(() => {
        if (user) {
            setShowLoginModal(false)
            fetch('/api/config')
                .then(res => res.json())
                .then(data => setConfig(data))
                .catch(err => console.error(err))
        }
    }, [user])

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setUploadFile(e.target.files[0])
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
            <div className="w-64 bg-gray-900 text-white p-4 hidden md:flex flex-col">
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
                    <div className="flex-1 bg-slate-100 flex items-start justify-center relative overflow-hidden">
                        {uploadFile ? (
                            <div className="w-full h-full p-4 md:p-8 overflow-y-auto custom-scrollbar">
                                <PDFViewer
                                    sessionId={sessionId}
                                    uploadFile={uploadFile}
                                    onWordClick={handleWordClick}
                                    onTextSelect={handleTextSelect}
                                    sessionId={sessionId}
                                    uploadFile={uploadFile}
                                    onWordClick={handleWordClick}
                                    onTextSelect={handleTextSelect}
                                    onAreaSelect={handleAreaSelect}
                                    jumpTarget={jumpTarget}
                                    onStatusChange={handleAnalysisStatusChange}
                                />
                            </div>
                        ) : (
                            <div className="bg-white p-8 rounded shadow text-center text-gray-400">
                                Select a PDF to view
                            </div>
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
                            isAnalyzing={isAnalyzing}
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
