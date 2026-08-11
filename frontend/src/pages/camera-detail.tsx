import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { posterUrl } from '../api/cameras.ts'
import { useCameras } from '../hooks/use-cameras.ts'
import { useLiveFrames } from '../hooks/use-live-frames.ts'
import { formatCount } from '../lib/format.ts'

type FactProps = {
    label: string
    children: ReactNode
}

function Fact({ label, children }: FactProps) {
    return (
        <div className="flex flex-col gap-0.5">
            <dt className="text-xs uppercase tracking-wide opacity-60">{label}</dt>
            <dd className="text-sm break-words text-heading">{children}</dd>
        </div>
    )
}

function CameraDetailPage() {
    const { cameraId = '' } = useParams()
    const { cameras, error, loading } = useCameras()
    const camera = cameras.find((entry) => entry.id === cameraId)
    const frameUrl = useLiveFrames(cameraId, camera?.online ?? false)
    const title = camera?.name ?? cameraId

    return (
        <main className="mx-auto max-w-5xl px-3 py-4 sm:px-6 sm:py-6 lg:px-8">
            <div className="mb-4 flex items-center gap-2">
                <Link
                    to="/livestream"
                    title="Zurück zu den Livestreams"
                    aria-label="Zurück zu den Livestreams"
                    className="btn btn-ghost btn-circle btn-sm sm:btn-md"
                >
                    <ArrowLeft className="size-5" aria-hidden={true} />
                </Link>
                <h2 className="min-w-0 flex-1 truncate text-xl font-semibold text-heading sm:text-2xl">
                    {title}
                </h2>
            </div>

            {error !== null && (
                <p role="alert" className="alert alert-error mb-4 text-sm">
                    {error}
                </p>
            )}

            {camera === undefined ? (
                <p className="opacity-70">
                    {loading ? 'Lade Vogelhaus …' : `Kein Vogelhaus mit der ID „${cameraId}" gefunden.`}
                </p>
            ) : (
                <>
                    <div className="card relative overflow-hidden border border-border bg-black/85">
                        <div className="aspect-video max-h-[70dvh]">
                            {frameUrl !== null ? (
                                <img
                                    src={frameUrl}
                                    alt={`Livebild von ${title}`}
                                    className="size-full object-contain"
                                />
                            ) : camera.has_poster ? (
                                <img
                                    src={`${posterUrl(camera.id)}?t=${camera.last_seen ?? ''}`}
                                    alt={`Letztes Bild von ${title}`}
                                    className="size-full object-contain opacity-50"
                                />
                            ) : (
                                <div className="flex size-full items-center justify-center text-sm text-white/40">
                                    Kein Bild verfügbar
                                </div>
                            )}
                        </div>

                        <div className="absolute left-2 top-2 flex gap-1">
                            {camera.online ? (
                                <span className="badge badge-sm badge-success">Live</span>
                            ) : (
                                <span className="badge badge-sm">Offline</span>
                            )}
                            {camera.recording && (
                                <span className="badge badge-sm badge-error animate-pulse">REC</span>
                            )}
                        </div>
                    </div>

                    {camera.description !== undefined && (
                        <p className="mt-3 text-sm opacity-80">{camera.description}</p>
                    )}

                    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
                        <Fact label="Standort">{camera.location ?? 'unbekannt'}</Fact>
                        <Fact label="Status">{camera.online ? 'Online' : 'Offline'}</Fact>
                        <Fact label="Bildrate">
                            {camera.fps !== null ? `${camera.fps} fps` : '–'}
                        </Fact>
                        <Fact label="Auflösung">
                            {camera.width !== null && camera.height !== null
                                ? `${camera.width}×${camera.height}`
                                : '–'}
                        </Fact>
                        <Fact label="Aufnahmen">
                            {formatCount(camera.video_count, 'Video', 'Videos')}
                        </Fact>
                    </dl>
                </>
            )}
        </main>
    )
}

export default CameraDetailPage
