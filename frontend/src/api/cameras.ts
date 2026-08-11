export type Camera = {
    id: string
    name?: string
    location?: string
    description?: string
    online: boolean
    recording: boolean
    fps: number | null
    last_seen: string | null
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

export type Video = {
    name: string
    title: string
    size: number
    created: string
}

export async function fetchVideos(cameraId: string, signal?: AbortSignal): Promise<Video[]> {
    const response = await fetch(`/api/cameras/${cameraId}/videos`, { signal })
    if (!response.ok) {
        throw new Error(`Aufnahmen konnten nicht geladen werden (HTTP ${response.status})`)
    }

    const body = (await response.json()) as { videos: Video[] }
    return body.videos
}

async function sendJson<T>(url: string, method: 'POST' | 'PUT' | 'DELETE', payload?: unknown): Promise<T> {
    const response = await fetch(url, {
        method,
        headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: payload === undefined ? undefined : JSON.stringify(payload),
    })

    const body = (await response.json().catch(() => ({}))) as T & { error?: string }
    if (!response.ok) {
        throw new Error(body.error ?? `Anfrage fehlgeschlagen (HTTP ${response.status})`)
    }

    return body
}

function videoStem(videoName: string) {
    return videoName.replace(/\.mp4$/, '')
}

export function startRecording(cameraId: string) {
    return sendJson(`/api/cameras/${cameraId}/recording/start`, 'POST')
}

export function stopRecording(cameraId: string) {
    return sendJson<{ video?: string }>(`/api/cameras/${cameraId}/recording/stop`, 'POST')
}

export function renameVideo(cameraId: string, videoName: string, name: string) {
    return sendJson(`/api/cameras/${cameraId}/videos/${videoStem(videoName)}/name`, 'PUT', { name })
}

export function deleteVideo(cameraId: string, videoName: string) {
    return sendJson(`/api/cameras/${cameraId}/videos/${videoStem(videoName)}`, 'DELETE')
}

export function videoUrl(cameraId: string, videoName: string) {
    return `/api/cameras/${cameraId}/videos/${videoName}`
}

export function posterUrl(cameraId: string) {
    return `/api/cameras/${cameraId}/poster.jpg`
}

export function liveSocketUrl(cameraId: string) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${location.host}/ws/live/${cameraId}`
}
