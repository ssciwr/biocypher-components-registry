import { useEffect, useState, type ReactNode } from 'react'
import { CheckIcon, ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet } from '../api/client'

type RepositoryCheckStatus = 'idle' | 'checking' | 'found' | 'missing' | 'blocked'
type RepositoryCheckMode = 'croissant-file' | 'none'
type CompletedRepositoryCheckStatus = Exclude<RepositoryCheckStatus, 'idle' | 'checking'>

type RepositoryUrlInputProps = Readonly<{
  checkMode?: RepositoryCheckMode
  inputClassName?: string
  label: ReactNode
  labelClassName?: string
  maxLength?: number
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
  value: string
}>

type CompletedRepositoryCheck = Readonly<{
  checkMode: RepositoryCheckMode
  repositoryUrl: string
  status: CompletedRepositoryCheckStatus
}>

const httpsUrlPattern = /^https:\/\/.+/i
const pendingStatusIcon = <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />
const statusIcons: Record<RepositoryCheckStatus, ReactNode> = {
  idle: pendingStatusIcon,
  checking: pendingStatusIcon,
  found: <CheckIcon className="h-5 w-5" aria-hidden="true" />,
  missing: <XMarkIcon className="h-5 w-5" aria-hidden="true" />,
  blocked: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
}
const repositoryCheckDisplays: Record<RepositoryCheckStatus, { className: string; text: string }> = {
  idle: { className: 'text-blue-700', text: 'Checking Croissant file' },
  checking: { className: 'text-blue-700', text: 'Checking Croissant file' },
  found: { className: 'text-emerald-600', text: 'Croissant file found at repository root' },
  missing: { className: 'text-red-600', text: "Croissant file not found at this repository link's root" },
  blocked: { className: 'text-red-600', text: 'Could not check Croissant file' },
}

/*
 * AI-Generated.
 */
export function RepositoryUrlInput({
  checkMode = 'croissant-file',
  inputClassName = 'h-12 rounded-xl border border-slate-200 bg-slate-50 px-4 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white',
  label,
  labelClassName = 'grid gap-2 text-sm font-semibold text-slate-950',
  maxLength,
  onChange,
  placeholder,
  required = false,
  value,
}: RepositoryUrlInputProps) {
  const [completedCheck, setCompletedCheck] = useState<CompletedRepositoryCheck | null>(null)
  const repositoryUrl = value.trim()
  const canCheckRepositoryUrl = checkMode === 'croissant-file' && httpsUrlPattern.test(repositoryUrl)
  let status: RepositoryCheckStatus = 'idle'
  if (canCheckRepositoryUrl) {
    status = completedCheck?.checkMode === checkMode && completedCheck.repositoryUrl === repositoryUrl
      ? completedCheck.status
      : 'checking'
  }
  const statusDisplay = repositoryCheckDisplays[status]

  useEffect(() => {
    if (!canCheckRepositoryUrl) {
      return
    }

    const controller = new AbortController()

    void checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet({
      query: { repository_url: repositoryUrl },
      signal: controller.signal,
    })
      .then((metadataResult) => {
        if (controller.signal.aborted) return
        if (metadataResult.error || !metadataResult.data) {
          setCompletedCheck({ checkMode, repositoryUrl, status: 'blocked' })
          return
        }
        const checkStatus = metadataResult.data.has_croissant_file ? 'found' : 'missing'
        setCompletedCheck({ checkMode, repositoryUrl, status: checkStatus })
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === 'AbortError') return
        setCompletedCheck({ checkMode, repositoryUrl, status: 'blocked' })
      })

    return () => controller.abort()
  }, [canCheckRepositoryUrl, checkMode, repositoryUrl])

  return (
    <label className={labelClassName}>
      <span>{label}</span>
      <input
        className={inputClassName}
        aria-invalid={canCheckRepositoryUrl && (status === 'missing' || status === 'blocked')}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type="url"
        value={value}
      />
      {status !== 'idle' ? (
        <span
          aria-live="polite"
          className={`inline-flex items-center gap-2 text-sm font-medium ${statusDisplay.className}`}
        >
          {statusIcons[status]}
          {statusDisplay.text}
        </span>
      ) : null}
    </label>
  )
}
