import CameraTile from '../components/camera-tile.tsx'
import { useCameras } from '../hooks/use-cameras.ts'

function LivestreamPage() {
    const { cameras, error, loading } = useCameras()
    const onlineCount = cameras.filter((camera) => camera.online).length

    return (
        <main className="mx-auto max-w-7xl px-3 py-4 sm:px-6 sm:py-6 lg:px-8 2xl:max-w-[96rem]">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h2 className="text-xl font-semibold text-heading sm:text-2xl">Livestreams</h2>
                {!loading && cameras.length > 0 && (
                    <p className="text-sm opacity-70">
                        {onlineCount} von {cameras.length} online
                    </p>
                )}
            </div>

            {error !== null && (
                <p role="alert" className="alert alert-error mb-4 text-sm">
                    {error}
                </p>
            )}

            {loading ? (
                <p className="opacity-70">Lade Kameras …</p>
            ) : cameras.length === 0 ? (
                <p className="opacity-70">
                    Noch keine Kamera bekannt. Sobald eine Kamera streamt, erscheint sie hier.
                </p>
            ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3 2xl:grid-cols-4">
                    {cameras.map((camera) => (
                        <CameraTile key={camera.id} camera={camera} />
                    ))}
                </div>
            )}
        </main>
    )
}

export default LivestreamPage
