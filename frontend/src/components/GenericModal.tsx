import { XMarkIcon } from '@heroicons/react/24/outline'
import type { ReactNode } from 'react'

type GenericModalProps = {
  title: string
  content: ReactNode
  open?: boolean
  onClose?: () => void
}

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="presentation"
      onClick={onClose}
    >
      <section
        aria-modal="true"
        aria-labelledby="generic-modal-title"
        className="w-full max-w-lg rounded-lg bg-white p-5 text-left shadow-xl dark:bg-zinc-900 sm:p-6"
        role="dialog"
        onClick={(event) => event.stopPropagation()}
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
            className="inline-flex h-9 w-9 flex-none cursor-pointer items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-950 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            type="button"
            onClick={onClose}
          >
            <XMarkIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="mt-4 text-sm leading-6 text-zinc-600 dark:text-zinc-300">{content}</div>
      </section>
    </div>
  )
}

export default GenericModal
