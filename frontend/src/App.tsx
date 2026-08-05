import { useCallback, useEffect, useRef, useState } from 'react'

const CAMERA_ID = 'vogelhaus-0'

type CameraInfo = {
    id: string
    name?: string
    location?: string
    description?: string
}

function App() {
    const imageRef = useRef<HTMLImageElement>(null)
    const [status, setStatus] = useState('')
    const [videos, setVideos] = useState<string[]>([])
    const [cameras, setCameras] = useState<CameraInfo[]>([])
    const [form, setForm] = useState({ name: '', location: '', description: '' })

    useEffect(() => {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
        const socket = new WebSocket(`${protocol}//${location.host}/ws/live/${CAMERA_ID}`)

        socket.onmessage = (message) => {
            const image = imageRef.current
            if (!image || !(message.data instanceof Blob)) return

            const imageUrl = URL.createObjectURL(message.data)
            image.onload = () => URL.revokeObjectURL(imageUrl)
            image.src = imageUrl
        }

        return () => socket.close()
    }, [])

    const loadVideos = useCallback(async () => {
        const response = await fetch(`/api/cameras/${CAMERA_ID}/videos`)
        setVideos((await response.json()).videos)
    }, [])

    const loadCameras = useCallback(async () => {
        const response = await fetch('/api/cameras')
        const cameras: CameraInfo[] = (await response.json()).cameras
        setCameras(cameras)

        const own = cameras.find((camera) => camera.id === CAMERA_ID)
        setForm({
            name: own?.name ?? '',
            location: own?.location ?? '',
            description: own?.description ?? '',
        })
    }, [])

    useEffect(() => {
        loadVideos()
        loadCameras()
    }, [loadVideos, loadCameras])

    async function startRecording() {
        const response = await fetch(`/api/cameras/${CAMERA_ID}/recording/start`, { method: 'POST' })
        const data = await response.json()
        setStatus(response.ok ? 'Recording...' : data.error)
    }

    async function stopRecording() {
        const response = await fetch(`/api/cameras/${CAMERA_ID}/recording/stop`, { method: 'POST' })
        const data = await response.json()
        setStatus(response.ok ? `Saved: ${data.video}` : data.error)
        loadVideos()
    }

    async function saveInfo() {
        await fetch(`/api/cameras/${CAMERA_ID}/info`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form),
        })
        loadCameras()
    }

    return (
        <div className="p-4 max-w-xl">
            <h1 className="text-2xl font-bold mb-4">Videoüberwachtes Vogelhaus</h1>

            <h2 className="text-xl font-semibold mb-2">Live Stream</h2>
            <img ref={imageRef} alt="Waiting for live stream..." className="max-w-full mb-4" />

            <h2 className="text-xl font-semibold mb-2">Recording</h2>
            <div className="mb-2">
                <button onClick={startRecording} className="border px-2 py-1 mr-2">
                    Start recording
                </button>
                <button onClick={stopRecording} className="border px-2 py-1">
                    Stop recording
                </button>
            </div>
            <p className="mb-4">{status}</p>

            <h2 className="text-xl font-semibold mb-2">Videos</h2>
            <ul className="list-disc pl-5 mb-4">
                {videos.map((video) => (
                    <li key={video}>
                        <a href={`/api/cameras/${CAMERA_ID}/videos/${video}`} className="underline">
                            {video}
                        </a>
                    </li>
                ))}
            </ul>

            <h2 className="text-xl font-semibold mb-2">Vogelhäuser</h2>
            <ul className="list-disc pl-5 mb-4">
                {cameras.map((camera) => (
                    <li key={camera.id}>
                        <b>{camera.name ?? camera.id}</b> ({camera.id})
                        {camera.location && ` – ${camera.location}`}
                        {camera.description && ` – ${camera.description}`}
                    </li>
                ))}
            </ul>

            <h3 className="font-semibold mb-2">Edit info für {CAMERA_ID}</h3>
            <div className="flex flex-col gap-2 max-w-xs">
                <input
                    placeholder="Name"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="border px-2 py-1"
                />
                <input
                    placeholder="Location"
                    value={form.location}
                    onChange={(e) => setForm({ ...form, location: e.target.value })}
                    className="border px-2 py-1"
                />
                <input
                    placeholder="Description"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="border px-2 py-1"
                />
                <button onClick={saveInfo} className="border px-2 py-1">
                    Save info
                </button>
            </div>
        </div>
    )
}

export default App
