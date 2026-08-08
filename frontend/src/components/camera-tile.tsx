import { Activity, Clock, Eye, Film, Monitor, VideoOff } from 'lucide-react'
import type { ComponentType } from 'react'

import { posterUrl, type Camera } from '../api/cameras.ts'
import { useLiveFrames } from '../hooks/use-live-frames.ts'
import { formatCount, formatRelativeTime } from '../lib/format.ts'

type StatProps = {
    icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean }>
    children: string
}

function Stat({ icon: Icon, children }: StatProps) {
    return (
        <li className="flex items-center gap-1">
            <Icon className="size-3.5 shrink-0" aria-hidden={true} />
            <span className="truncate">{children}</span>
        </li>
    )
}

type CameraTileProps = {
    camera: Camera
}

function CameraTile({ camera }: CameraTileProps) {
    const frameUrl = useLiveFrames(camera.id, camera.online)
    const title = camera.name ?? camera.id

    return (
        <article className="card overflow-hidden border border-border bg-surface">
            <div className="relative aspect-video bg-black/85">
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
                    <div className="flex size-full items-center justify-center">
                        <VideoOff className="size-10 text-white/30" aria-hidden={true} />
                    </div>
                )}

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

            <div className="flex flex-col gap-1 p-3">
                <h3 className="truncate font-semibold text-heading" title={camera.id}>
                    {title}
                </h3>
                {camera.location !== undefined && (
                    <p className="truncate text-xs opacity-70">{camera.location}</p>
                )}

                <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs opacity-70">
                    {camera.online ? (
                        <>
                            {camera.fps !== null && <Stat icon={Activity}>{`${camera.fps} fps`}</Stat>}
                            <Stat icon={Eye}>{formatCount(camera.viewers, 'Zuschauer', 'Zuschauer')}</Stat>
                        </>
                    ) : (
                        <Stat icon={Clock}>{formatRelativeTime(camera.last_seen)}</Stat>
                    )}

                    {camera.width !== null && camera.height !== null && (
                        <Stat icon={Monitor}>{`${camera.width}×${camera.height}`}</Stat>
                    )}
                    <Stat icon={Film}>{formatCount(camera.video_count, 'Video', 'Videos')}</Stat>
                </ul>
            </div>
        </article>
    )
}

export default CameraTile
