import { useState, useEffect } from 'react'

function App() {
    const [config, setConfig] = useState<any>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetch('/api/config')
            .then(res => res.json())
            .then(data => {
                setConfig(data)
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to fetch config', err)
                setLoading(false)
            })
    }, [])

    return (
        <div className="min-h-screen bg-gray-100 flex items-center justify-center">
            <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
                <h1 className="text-2xl font-bold mb-4 text-blue-600">PaperTerrace React</h1>
                <p className="mb-4 text-gray-700">frontend migration in progress...</p>

                <div className="bg-gray-50 p-4 rounded border border-gray-200">
                    <h2 className="font-semibold mb-2">Backend Connection Status:</h2>
                    {loading ? (
                        <p className="text-gray-500">Connecting...</p>
                    ) : config ? (
                        <div className="text-green-600">
                            <p>✅ Connected to FastAPI</p>
                            <pre className="text-xs mt-2 text-gray-500 overflow-auto">
                                {JSON.stringify(config, null, 2)}
                            </pre>
                        </div>
                    ) : (
                        <p className="text-red-500">❌ Failed to connect</p>
                    )}
                </div>
            </div>
        </div>
    )
}

export default App
