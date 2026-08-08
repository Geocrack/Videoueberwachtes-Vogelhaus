import { useEffect, useState } from 'react'

import { fetchCameras, type Camera } from '../api/cameras.ts'

const POLL_INTERVAL_MS = 5000

export function useCameras(intervalMs = POLL_INTERVAL_MS) {
    const [cameras, setCameras] = useState<Camera[]>([])
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const controller = new AbortController()
        let timer = 0

        async function poll() {
            if (!document.hidden) {
                try {
                    setCameras(await fetchCameras(controller.signal))
                    setError(null)
                } catch (cause) {
                    if (controller.signal.aborted) return
                    setError(cause instanceof Error ? cause.message : String(cause))
                }
                setLoading(false)
            }

            timer = window.setTimeout(poll, intervalMs)
        }

        function pollNow() {
            if (document.hidden) return
            window.clearTimeout(timer)
            void poll()
        }

        void poll()
        document.addEventListener('visibilitychange', pollNow)

        return () => {
            controller.abort()
            window.clearTimeout(timer)
            document.removeEventListener('visibilitychange', pollNow)
        }
    }, [intervalMs])

    return { cameras, error, loading }
}
