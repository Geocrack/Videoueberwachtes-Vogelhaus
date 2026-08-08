import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import Header from './components/header.tsx'
import LivestreamPage from './pages/livestream.tsx'

function App() {
    return (
        <BrowserRouter>
            <div className="min-h-dvh">
                <Header />
                <Routes>
                    <Route path="/livestream" element={<LivestreamPage />} />
                    <Route path="*" element={<Navigate to="/livestream" replace />} />
                </Routes>
            </div>
        </BrowserRouter>
    )
}

export default App
