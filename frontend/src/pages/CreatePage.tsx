import { useState } from 'react'
import { ArrowPathIcon, DocumentPlusIcon } from '@heroicons/react/24/outline'
import { metadataDraftStorageKey } from './createMetadata/storage'


function hasSavedMetadataDraft() {
  try {
    return Boolean(globalThis.localStorage.getItem(metadataDraftStorageKey))
  } catch (storageError) {
    console.warn('Could not check saved metadata draft.', storageError)
    return false
  }
}


function CreatePage() {
  const [hasDraft] = useState(hasSavedMetadataDraft)

  return (
    <section className="min-h-[calc(100vh-8rem)] bg-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <h1 className="max-w-5xl text-4xl font-bold tracking-normal text-slate-950 md:text-5xl">
          Create a Metadata File for an Adapter
        </h1>

        <div className="mt-12 grid max-w-4xl gap-5 md:grid-cols-2">
          <article className="flex min-h-72 flex-col rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Blank start
            </span>
            <DocumentPlusIcon className="mt-5 h-8 w-8 text-blue-600" aria-hidden="true" />
            <h2 className="mt-5 text-2xl font-bold text-slate-950">
              Enter adapter details into a form
            </h2>
            <p className="mt-5 max-w-md text-base leading-6 text-slate-600">
              Build adapter metadata step by step and export it as a Croissant file
            </p>
            <span className="flex-1" />
            <a
              className="mt-10 inline-flex h-12 w-fit items-center justify-center rounded-lg bg-blue-600 px-5 text-base font-semibold text-white hover:bg-blue-700"
              href="/create/adapter-metadata?start=1"
            >
              Start from scratch
            </a>
          </article>

          <article className="flex min-h-72 flex-col rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Continue
            </span>
            <ArrowPathIcon className="mt-5 h-8 w-8 text-slate-500" aria-hidden="true" />
            <h2 className="mt-5 text-2xl font-bold text-slate-950">
              Resume previous session
            </h2>
            <p className="mt-5 max-w-md text-base leading-6 text-slate-600">
              Continue editing metadata that was previously saved in this browser.
            </p>
            <span className="flex-1" />
            {hasDraft ? (
              <a
                className="mt-10 inline-flex h-12 w-fit items-center justify-center rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 hover:border-blue-300"
                href="/create/adapter-metadata?resume=1"
              >
                Resume session
              </a>
            ) : (
              <button
                className="mt-10 inline-flex h-12 w-fit cursor-not-allowed items-center justify-center rounded-lg border border-slate-200 bg-white px-5 text-base font-semibold text-slate-950 opacity-60"
                disabled
                type="button"
              >
                Resume session
              </button>
            )}
          </article>
        </div>
      </div>
    </section>
  )
}

export default CreatePage
