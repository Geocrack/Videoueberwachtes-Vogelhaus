import { useEffect, useState } from 'react'

import { fetchVideos, type Video } from '../api/cameras.ts'

export function useVideos(cameraId: string, videoCount?: number) {
    const [videos, setVideos] = useState<Video[]>([])
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [reloadToken, setReloadToken] = useState(0)

    useEffect(() => {
        const controller = new AbortController()

        async function load() {
            try {
                setVideos(await fetchVideos(cameraId, controller.signal))
                setError(null)
            } catch (cause) {
                if (controller.signal.aborted) return
                setError(cause instanceof Error ? cause.message : String(cause))
            }
            setLoading(false)
        }

        void load()

        return () => controller.abort()
    }, [cameraId, videoCount, reloadToken])

    return { videos, error, loading, reload: () => setReloadToken((token) => token + 1) }
}
