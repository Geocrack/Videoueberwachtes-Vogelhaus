export type Camera = {
    id: string
    name?: string
    location?: string
    description?: string
    online: boolean
    recording: boolean
    viewers: number
    fps: number | null
    first_seen: string | null
    last_seen: string | null
    frames_total: number
    width: number | null
    height: number | null
    video_count: number
    has_poster: boolean
}

export async function fetchCameras(signal?: AbortSignal): Promise<Camera[]> {
    const response = await fetch('/api/cameras', { signal })
    if (!response.ok) {
        throw new Error(`Kameraliste konnte nicht geladen werden (HTTP ${response.status})`)
    }

    const body = (await response.json()) as { cameras: Camera[] }
    return body.cameras
}

export function posterUrl(cameraId: string) {
    return `/api/cameras/${cameraId}/poster.jpg`
}

export function liveSocketUrl(cameraId: string) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${location.host}/ws/live/${cameraId}`
}
