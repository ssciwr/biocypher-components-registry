import { useEffect, useState, type ReactNode } from 'react'
import { CheckIcon, ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet } from '../api/client'

type RepositoryCheckStatus = 'idle' | 'CHECKING' | 'FOUND' | 'NOT_FOUND' | 'UNAVAILABLE' | 'BLOCKED'
type RepositoryCheckMode = 'croissant-file' | 'none'
type CompletedRepositoryCheckStatus = Exclude<RepositoryCheckStatus, 'idle' | 'CHECKING'>

type RepositoryUrlInputProps = Readonly<{
  checkMode?: RepositoryCheckMode
  inputClassName?: string
  label: ReactNode
  labelClassName?: string
  maxLength?: number
  onChange: (value: string) => void
  onValidatedRepositoryChange?: (repositoryUrl: string | null) => void
  placeholder?: string
  required?: boolean
  showValidationFeedback?: boolean
  value: string
}>

type CompletedRepositoryCheck = Readonly<{
  checkMode: RepositoryCheckMode
  repositoryUrl: string
  status: CompletedRepositoryCheckStatus
  message: string
}>

// Allow the backend's 60-second repository check to return its diagnostics.
const repositoryCheckTimeoutMs = 65_000
const connectionMessage = 'Unable to connect to service. Edit the URL to try again.'
const httpsUrlPattern = /^https:\/\/.+/i
const pendingStatusIcon = <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />
const statusIcons: Record<RepositoryCheckStatus, ReactNode> = {
  idle: pendingStatusIcon,
  CHECKING: pendingStatusIcon,
  FOUND: <CheckIcon className="h-5 w-5" aria-hidden="true" />,
  NOT_FOUND: <XMarkIcon className="h-5 w-5" aria-hidden="true" />,
  BLOCKED: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
  UNAVAILABLE: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
}
const repositoryCheckDisplays: Record<RepositoryCheckStatus, { className: string; text: string }> = {
  idle: { className: 'text-blue-700', text: 'Checking Croissant file' },
  CHECKING: { className: 'text-blue-700', text: 'Checking Croissant file' },
  FOUND: { className: 'text-emerald-600', text: 'Croissant file found at repository root' },
  NOT_FOUND: { className: 'text-red-600', text: "Croissant file not found at repository root" },
  BLOCKED: { className: 'text-red-600', text: 'Enter the source code repository URL for this adapter.' },
  UNAVAILABLE: { className: 'text-red-600', text: connectionMessage },
}

function isRegistryPageUrl(repositoryUrl: string): boolean {
  if (!URL.canParse(repositoryUrl)) return false
  const address = new URL(repositoryUrl)
  return address.origin === globalThis.location.origin || address.hostname === 'registry.biocypher.org'
}

export function RepositoryUrlInput({
  checkMode = 'croissant-file',
  inputClassName = 'h-12 rounded-xl border border-slate-200 bg-slate-50 px-4 text-base font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:bg-white',
  label,
  labelClassName = 'grid gap-2 text-sm font-semibold text-slate-950',
  maxLength,
  onChange,
  onValidatedRepositoryChange,
  placeholder,
  required = false,
  showValidationFeedback = false,
  value,
}: RepositoryUrlInputProps) {
  const [completedCheck, setCompletedCheck] = useState<CompletedRepositoryCheck | null>(null)
  const [hasEditedRepository, setHasEditedRepository] = useState(false)
  const repositoryUrl = value.trim()
  const isRegistryPage = checkMode === 'croissant-file' && isRegistryPageUrl(repositoryUrl)
  const canCheckRepositoryUrl = checkMode === 'croissant-file' && httpsUrlPattern.test(repositoryUrl) && !isRegistryPage
  const showRepositoryFeedback = showValidationFeedback || hasEditedRepository
  let status: RepositoryCheckStatus = isRegistryPage ? 'BLOCKED' : 'idle'
  if (canCheckRepositoryUrl) {
    status = completedCheck?.checkMode === checkMode && completedCheck.repositoryUrl === repositoryUrl
      ? completedCheck.status
      : 'CHECKING'
  }
  const statusDisplay = repositoryCheckDisplays[status]

  useEffect(() => {
    onValidatedRepositoryChange?.(status === 'FOUND' ? repositoryUrl : null)
  }, [onValidatedRepositoryChange, repositoryUrl, status])

  useEffect(() => {
    if (!canCheckRepositoryUrl) {
      return
    }

    const controller = new AbortController()
    let retryCount = 0
    let timer: ReturnType<typeof setTimeout>

    function handleUnavailable(message: string, transient: boolean) {
      if (controller.signal.aborted) return
      if (transient && retryCount < 2) {
        retryCount += 1
        timer = setTimeout(() => void checkRepository(), retryCount * 1000)
        return
      }
      setCompletedCheck({ checkMode, repositoryUrl, status: 'UNAVAILABLE', message })
    }

    async function checkRepository() {
      const timeout = new AbortController()
      const deadline = setTimeout(() => timeout.abort(), repositoryCheckTimeoutMs)
      const signal = AbortSignal.any([controller.signal, timeout.signal])
      try {
        const response = await checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet({
          query: { repository_url: repositoryUrl },
          signal,
        })
        if (controller.signal.aborted) return
        const result = response.data
        if (response.response?.status === 400 || response.response?.status === 422) {
          setCompletedCheck({ checkMode, repositoryUrl, status: 'BLOCKED', message: '' })
        } else if (!result?.status || timeout.signal.aborted) {
          handleUnavailable(connectionMessage, !timeout.signal.aborted)
        } else if (result.status === 'UNAVAILABLE') {
          handleUnavailable(result.message, result.reason_code === 'REMOTE_TEMPORARY')
        } else {
          setCompletedCheck({ checkMode, repositoryUrl, status: result.status, message: result.message })
        }
      } catch {
        handleUnavailable(connectionMessage, !timeout.signal.aborted)
      } finally {
        clearTimeout(deadline)
      }
    }
    timer = setTimeout(() => void checkRepository(), 200)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }

  }, [canCheckRepositoryUrl, checkMode, repositoryUrl])

  return (
    <label className={labelClassName}>
      <span>{label}</span>
      <input
        className={inputClassName}
        aria-invalid={showRepositoryFeedback && (status === 'NOT_FOUND' || status === 'BLOCKED')}
        maxLength={maxLength}
        onChange={(event) => {
          setHasEditedRepository(true)
          if (event.target.value.trim() !== repositoryUrl) setCompletedCheck(null)
          onChange(event.target.value)
        }}
        placeholder={placeholder}
        required={required}
        type="url"
        value={value}
      />
      {showRepositoryFeedback && status !== 'idle' ? (
        <span
          aria-live="polite"
          className={`inline-flex items-center gap-2 text-sm font-medium ${statusDisplay.className}`}
        >
          {statusIcons[status]}
          {status === 'UNAVAILABLE' ? completedCheck?.message ?? statusDisplay.text : statusDisplay.text}
        </span>
      ) : null}
    </label>
  )
}
