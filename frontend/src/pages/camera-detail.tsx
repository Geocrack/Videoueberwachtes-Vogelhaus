import { ArrowLeft, Circle, Download, Pencil, Play, Square, Trash2, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import ConfirmDialog from '../components/confirm-dialog.tsx'
import NameDialog from '../components/name-dialog.tsx'
import {
    deleteVideo,
    posterUrl,
    renameVideo,
    startRecording,
    stopRecording,
    videoUrl,
    type Video,
} from '../api/cameras.ts'
import { useCameras } from '../hooks/use-cameras.ts'
import { useLiveFrames } from '../hooks/use-live-frames.ts'
import { useVideos } from '../hooks/use-videos.ts'
import { formatCount, formatFileSize, formatTimestamp } from '../lib/format.ts'

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

type DialogState =
    | { mode: 'name'; videoName: string; title: string; fresh: boolean }
    | { mode: 'delete'; video: Video }
    | null

function videoLabel(video: Video) {
    return video.title !== '' ? video.title : formatTimestamp(video.created)
}

function CameraDetailPage() {
    const { cameraId = '' } = useParams()
    const { cameras, error, loading, reload: reloadCameras } = useCameras()
    const camera = cameras.find((entry) => entry.id === cameraId)
    const {
        videos,
        error: videosError,
        loading: videosLoading,
        reload: reloadVideos,
    } = useVideos(cameraId, camera?.video_count)

    const [selectedName, setSelectedName] = useState<string | null>(null)
    const [dialog, setDialog] = useState<DialogState>(null)
    const [busy, setBusy] = useState(false)
    const [actionError, setActionError] = useState<string | null>(null)

    const frameUrl = useLiveFrames(cameraId, camera?.online ?? false)
    const title = camera?.name ?? cameraId
    const recording = camera?.recording ?? false
    const selectedVideo = videos.find((video) => video.name === selectedName) ?? null

    async function run(action: () => Promise<void>) {
        setBusy(true)
        setActionError(null)
        try {
            await action()
        } catch (cause) {
            setActionError(cause instanceof Error ? cause.message : String(cause))
        }
        setBusy(false)
    }

    function handleRecordClick() {
        void run(async () => {
            if (!recording) {
                await startRecording(cameraId)
                reloadCameras()
                return
            }

            const saved = await stopRecording(cameraId)
            reloadCameras()
            reloadVideos()

            if (saved.video !== undefined) {
                setDialog({ mode: 'name', videoName: saved.video, title: '', fresh: true })
            }
        })
    }

    function handleNameConfirm(name: string) {
        const current = dialog
        setDialog(null)
        if (current?.mode !== 'name') return

        void run(async () => {
            await renameVideo(cameraId, current.videoName, name)
            reloadVideos()
        })
    }

    function handleDelete(videoName: string) {
        setDialog(null)

        void run(async () => {
            await deleteVideo(cameraId, videoName)
            reloadCameras()
            reloadVideos()
        })
    }

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

                {camera !== undefined && (
                    <button
                        type="button"
                        onClick={handleRecordClick}
                        disabled={busy || (!recording && !camera.online)}
                        title={
                            !recording && !camera.online
                                ? 'Kamera ist offline'
                                : recording
                                  ? 'Aufnahme sofort beenden'
                                  : 'Aufnahme starten'
                        }
                        className={`btn btn-sm shrink-0 sm:btn-md ${recording ? 'btn-error' : 'btn-primary'}`}
                    >
                        {recording ? (
                            <Square className="size-4" aria-hidden={true} />
                        ) : (
                            <Circle className="size-4" aria-hidden={true} />
                        )}
                        <span className="hidden sm:inline">
                            {busy ? 'Moment …' : recording ? 'Aufnahme beenden' : 'Aufnehmen'}
                        </span>
                    </button>
                )}
            </div>

            {[error, actionError].map(
                (message, index) =>
                    message !== null && (
                        <p key={index} role="alert" className="alert alert-error mb-4 text-sm">
                            {message}
                        </p>
                    ),
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
                            {recording && (
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

                    {selectedVideo !== null && (
                        <section className="mt-6 border-t border-border pt-4">
                            <h3 className="mb-3 text-lg font-semibold text-heading">Wiedergabe</h3>

                            <div className="rounded-box border border-accent bg-surface p-2">
                                <div className="mb-2 flex items-center gap-2 px-1">
                                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-heading">
                                        {videoLabel(selectedVideo)}
                                    </span>
                                    <span className="hidden shrink-0 text-xs opacity-60 sm:inline">
                                        {formatTimestamp(selectedVideo.created)}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => setSelectedName(null)}
                                        title="Wiedergabe schließen"
                                        aria-label="Wiedergabe schließen"
                                        className="btn btn-ghost btn-circle btn-xs shrink-0 sm:btn-sm"
                                    >
                                        <X className="size-4" aria-hidden={true} />
                                    </button>
                                </div>

                                <video
                                    key={selectedVideo.name}
                                    src={videoUrl(camera.id, selectedVideo.name)}
                                    controls
                                    autoPlay
                                    playsInline
                                    className="aspect-video max-h-[60dvh] w-full rounded-box bg-black/85"
                                />
                            </div>
                        </section>
                    )}

                    <section className="mt-6 border-t border-border pt-4">
                        <h3 className="mb-3 flex items-baseline gap-2 text-lg font-semibold text-heading">
                            Aufnahmen
                            {videos.length > 0 && (
                                <span className="text-sm font-normal opacity-60">{videos.length}</span>
                            )}
                        </h3>

                        {videosError !== null && (
                            <p role="alert" className="alert alert-error mb-2 text-sm">
                                {videosError}
                            </p>
                        )}

                        {videosLoading ? (
                            <p className="opacity-70">Lade Aufnahmen …</p>
                        ) : videos.length === 0 ? (
                            <p className="opacity-70">
                                Noch keine Aufnahmen. Starte eine Aufnahme, während die Kamera live ist.
                            </p>
                        ) : (
                            <ul className="flex flex-col gap-2">
                                {videos.map((video) => (
                                    <li
                                        key={video.name}
                                        className={`flex items-center gap-1 rounded-box border bg-surface p-2 ${
                                            video.name === selectedName ? 'border-accent' : 'border-border'
                                        }`}
                                    >
                                        <button
                                            type="button"
                                            onClick={() => setSelectedName(video.name)}
                                            className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                        >
                                            <Play className="size-4 shrink-0" aria-hidden={true} />
                                            <span className="min-w-0">
                                                <span className="block truncate text-sm text-heading">
                                                    {videoLabel(video)}
                                                </span>
                                                <span className="block truncate text-xs opacity-60">
                                                    {video.title !== ''
                                                        ? `${formatTimestamp(video.created)} · ${formatFileSize(video.size)}`
                                                        : formatFileSize(video.size)}
                                                </span>
                                            </span>
                                        </button>

                                        <button
                                            type="button"
                                            onClick={() =>
                                                setDialog({
                                                    mode: 'name',
                                                    videoName: video.name,
                                                    title: video.title,
                                                    fresh: false,
                                                })
                                            }
                                            title={`${videoLabel(video)} umbenennen`}
                                            aria-label={`${videoLabel(video)} umbenennen`}
                                            className="btn btn-ghost btn-circle btn-sm shrink-0"
                                        >
                                            <Pencil className="size-4" aria-hidden={true} />
                                        </button>

                                        <a
                                            href={videoUrl(camera.id, video.name)}
                                            download={video.name}
                                            title={`${videoLabel(video)} herunterladen`}
                                            aria-label={`${videoLabel(video)} herunterladen`}
                                            className="btn btn-ghost btn-circle btn-sm shrink-0"
                                        >
                                            <Download className="size-4" aria-hidden={true} />
                                        </a>

                                        <button
                                            type="button"
                                            onClick={() => setDialog({ mode: 'delete', video })}
                                            title={`${videoLabel(video)} löschen`}
                                            aria-label={`${videoLabel(video)} löschen`}
                                            className="btn btn-ghost btn-circle btn-sm shrink-0 text-error"
                                        >
                                            <Trash2 className="size-4" aria-hidden={true} />
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                </>
            )}

            {dialog?.mode === 'name' && (
                <NameDialog
                    key={dialog.videoName}
                    heading={dialog.fresh ? 'Aufnahme gespeichert – benennen?' : 'Aufnahme umbenennen'}
                    initialValue={dialog.title}
                    cancelLabel={dialog.fresh ? 'Ohne Namen behalten' : 'Abbrechen'}
                    onCancel={() => setDialog(null)}
                    onConfirm={handleNameConfirm}
                    onDelete={dialog.fresh ? () => handleDelete(dialog.videoName) : undefined}
                />
            )}

            {dialog?.mode === 'delete' && (
                <ConfirmDialog
                    heading="Aufnahme löschen"
                    message={`„${videoLabel(dialog.video)}" wird endgültig gelöscht.`}
                    confirmLabel="Löschen"
                    onCancel={() => setDialog(null)}
                    onConfirm={() => handleDelete(dialog.video.name)}
                />
            )}
        </main>
    )
}

export default CameraDetailPage
