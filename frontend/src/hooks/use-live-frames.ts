import { useEffect, useRef, useState } from 'react'

import { liveSocketUrl } from '../api/cameras.ts'

const MIN_RETRY_MS = 1000
const MAX_RETRY_MS = 15000

export function useLiveFrames(cameraId: string, enabled: boolean) {
    const [frameUrl, setFrameUrl] = useState<string | null>(null)
    const currentUrl = useRef<string | null>(null)

    useEffect(() => {
        if (!enabled) return

        let socket: WebSocket | null = null
        let retryTimer = 0
        let retryDelay = MIN_RETRY_MS
        let stopped = false

        function connect() {
            socket = new WebSocket(liveSocketUrl(cameraId))

            socket.onopen = () => {
                retryDelay = MIN_RETRY_MS
            }

            socket.onmessage = (message) => {
                if (!(message.data instanceof Blob)) return

                const nextUrl = URL.createObjectURL(message.data)
                if (currentUrl.current !== null) URL.revokeObjectURL(currentUrl.current)
                currentUrl.current = nextUrl
                setFrameUrl(nextUrl)
            }

            socket.onclose = () => {
                if (stopped) return
                retryTimer = window.setTimeout(connect, retryDelay)
                retryDelay = Math.min(retryDelay * 2, MAX_RETRY_MS)
            }
        }

        connect()

        return () => {
            stopped = true
            window.clearTimeout(retryTimer)
            socket?.close()

            if (currentUrl.current !== null) {
                URL.revokeObjectURL(currentUrl.current)
                currentUrl.current = null
            }
            setFrameUrl(null)
        }
    }, [cameraId, enabled])

    return frameUrl
}
