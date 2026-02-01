import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { AuthProvider } from './contexts/AuthContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    // React.StrictMode causes double initialization in development, 
    // leading to duplicate API calls. Disabling for cleaner logs.
    // <React.StrictMode>
    <AuthProvider>
        <App />
    </AuthProvider>
    // </React.StrictMode>,
)
