import { cloneElement, isValidElement, type ReactElement, type ReactNode, useState } from 'react'

type ModalElement = ReactElement<{
  open?: boolean
  onClose?: () => void
}>

type LinkToModalProps = {
  children: ReactNode
  modal: ModalElement
}

/**
 * A helper so you can easily create a modal based around any JSX element.
 * @param children
 * @param modal
 * @constructor
 */
function LinkToModal({ children, modal }: LinkToModalProps) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        className="cursor-pointer rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
        type="button"
        onClick={() => setOpen(true)}
      >
        {children}
      </button>
      {isValidElement(modal) && cloneElement(modal, { open, onClose: () => setOpen(false) })}
    </>
  )
}

export default LinkToModal
