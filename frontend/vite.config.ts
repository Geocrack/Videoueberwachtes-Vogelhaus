import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
    plugins: [
        react(),
        tailwindcss()
    ],
    server: {
        // During development, forward API and WebSocket requests to the
        proxy: {
            '/api': 'http://localhost:5000',
            '/ws': {
                target: 'ws://localhost:5000',
                ws: true,
            },
        },
    },
})
