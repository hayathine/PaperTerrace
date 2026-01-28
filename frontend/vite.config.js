import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
            '/stamps': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
            '/analyze-pdf-json': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
            '/stream': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            }
        }
    }
})