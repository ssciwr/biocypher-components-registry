import type { ReactNode } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'

type GenericModalProps = Readonly<{
  title: string
  content: ReactNode
  open?: boolean
  onClose?: () => void
}>

/**
 * A helper so you can create a Modal quickly for any content you need to show, or that is not important to show immediately, but have available by reference.
 * @param title
 * @param content
 * @param open
 * @param onClose
 * @constructor
 */
function GenericModal({ title, content, open = false, onClose }: GenericModalProps) {
  if (!open) return null

  return (
    <dialog
      aria-labelledby="generic-modal-title"
      className="fixed inset-0 z-50 m-auto w-[calc(100%-2rem)] max-w-lg rounded-lg bg-white p-6 text-left shadow-xl backdrop:bg-black/40 dark:bg-zinc-900"
      onCancel={(event) => {
        event.preventDefault()
        onClose?.()
      }}
      open
    >
      <div className="flex items-start justify-between gap-4">
        <h2
          className="m-0 text-xl font-semibold text-zinc-950 dark:text-zinc-50"
          id="generic-modal-title"
        >
          {title}
        </h2>
        <button
          aria-label="Close modal"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          onClick={onClose}
          type="button"
        >
          <XMarkIcon className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <div className="mt-4 text-sm leading-6 text-zinc-600 dark:text-zinc-300">{content}</div>
    </dialog>
  )
}

export default GenericModal
