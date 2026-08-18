import { useEffect, useRef, useState } from 'react'

type NameDialogProps = {
    heading: string
    initialValue: string
    cancelLabel: string
    onCancel: () => void
    onConfirm: (name: string) => void
    onDelete?: () => void
}

function NameDialog({ heading, initialValue, cancelLabel, onCancel, onConfirm, onDelete }: NameDialogProps) {
    const dialogRef = useRef<HTMLDialogElement>(null)
    const [value, setValue] = useState(initialValue)

    useEffect(() => {
        dialogRef.current?.showModal()
    }, [])

    return (
        <dialog
            ref={dialogRef}
            className="modal modal-bottom sm:modal-middle"
            onCancel={(event) => {
                event.preventDefault()
                onCancel()
            }}
        >
            <form
                className="modal-box border border-border bg-surface"
                onSubmit={(event) => {
                    event.preventDefault()
                    onConfirm(value.trim())
                }}
            >
                <h3 className="mb-3 text-lg font-semibold text-heading">{heading}</h3>

                <input
                    type="text"
                    autoFocus
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    maxLength={120}
                    placeholder="z. B. Blaumeise am Futterhaus"
                    aria-label="Name der Aufnahme"
                    className="input input-bordered w-full"
                />
                <p className="mt-2 text-xs opacity-60">
                    Ohne Namen wird die Aufnahme mit ihrem Zeitpunkt angezeigt.
                </p>

                <div className="modal-action flex-wrap justify-between gap-2">
                    {onDelete !== undefined ? (
                        <button
                            type="button"
                            onClick={onDelete}
                            className="btn btn-ghost btn-sm text-error sm:btn-md"
                        >
                            Aufnahme löschen
                        </button>
                    ) : (
                        <span />
                    )}

                    <span className="flex gap-2">
                        <button type="button" onClick={onCancel} className="btn btn-ghost btn-sm sm:btn-md">
                            {cancelLabel}
                        </button>
                        <button type="submit" className="btn btn-primary btn-sm sm:btn-md">
                            Speichern
                        </button>
                    </span>
                </div>
            </form>

            <div className="modal-backdrop">
                <button type="button" onClick={onCancel} aria-label="Dialog schließen" />
            </div>
        </dialog>
    )
}

export default NameDialog
