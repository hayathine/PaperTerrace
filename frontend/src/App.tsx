import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar/Sidebar'
import PDFViewer from './components/PDF/PDFViewer'

function App() {
    const [config, setConfig] = useState<any>(null)
    const [uploadFile, setUploadFile] = useState<File | null>(null)

    // Sidebar State
    const [sessionId] = useState(`session-${Math.random().toString(36).substring(2, 11)}`)
    const [activeTab, setActiveTab] = useState('chat')
    const [selectedWord, setSelectedWord] = useState<string | undefined>(undefined)

    useEffect(() => {
        fetch('/api/config')
            .then(res => res.json())
            .then(data => setConfig(data))
            .catch(err => console.error(err))
    }, [])

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setUploadFile(e.target.files[0])
        }
    }

    const handleWordClick = (word: string) => {
        setSelectedWord(word)
        setActiveTab('dict')
    }

    return (
        <div className="flex h-screen w-full bg-gray-100 overflow-hidden">
            {/* ... (Sidebar Placeholder lines 25-48) */}
            <div className="w-64 bg-gray-900 text-white p-4 hidden md:flex flex-col">
                <h1 className="text-xl font-bold mb-8">PaperTerrace</h1>
                <div className="flex-1">
                    <p className="text-gray-400 text-sm">Validating React Migration...</p>
                    {config && <p className="text-green-400 text-xs mt-2">● API Connected</p>}
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
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}

export default App
