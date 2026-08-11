import { useEffect, useRef } from 'react'

type ConfirmDialogProps = {
    heading: string
    message: string
    confirmLabel: string
    onCancel: () => void
    onConfirm: () => void
}

function ConfirmDialog({ heading, message, confirmLabel, onCancel, onConfirm }: ConfirmDialogProps) {
    const dialogRef = useRef<HTMLDialogElement>(null)

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
            <div className="modal-box border border-border bg-surface">
                <h3 className="mb-2 text-lg font-semibold text-heading">{heading}</h3>
                <p className="text-sm break-words opacity-80">{message}</p>

                <div className="modal-action">
                    <button type="button" onClick={onCancel} className="btn btn-ghost btn-sm sm:btn-md">
                        Abbrechen
                    </button>
                    <button
                        type="button"
                        autoFocus
                        onClick={onConfirm}
                        className="btn btn-error btn-sm sm:btn-md"
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>

            <div className="modal-backdrop">
                <button type="button" onClick={onCancel} aria-label="Dialog schließen" />
            </div>
        </dialog>
    )
}

export default ConfirmDialog
