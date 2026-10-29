import { useEffect, useState, type ReactNode } from 'react'
import { CheckIcon, ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet } from '../api/client'

type RepositoryCheckStatus = 'idle' | 'CHECKING' | 'FOUND' | 'NOT_FOUND' | 'UNAVAILABLE'
type RepositoryCheckMode = 'croissant-file' | 'none'
type CompletedRepositoryCheckStatus = Exclude<RepositoryCheckStatus, 'idle' | 'CHECKING'>

type RepositoryUrlInputProps = Readonly<{
  checkMode?: RepositoryCheckMode
  inputClassName?: string
  label: ReactNode
  labelClassName?: string
  maxLength?: number
  onChange: (value: string) => void
  onValidationChange?: (isValid: boolean) => void
  placeholder?: string
  required?: boolean
  value: string
}>

type CompletedRepositoryCheck = Readonly<{
  checkMode: RepositoryCheckMode
  repositoryUrl: string
  status: CompletedRepositoryCheckStatus
  message: string
}>

const httpsUrlPattern = /^https:\/\/.+/i
const pendingStatusIcon = <span className="h-2.5 w-2.5 rounded-full bg-current" aria-hidden="true" />
const statusIcons: Record<RepositoryCheckStatus, ReactNode> = {
  idle: pendingStatusIcon,
  CHECKING: pendingStatusIcon,
  FOUND: <CheckIcon className="h-5 w-5" aria-hidden="true" />,
  NOT_FOUND: <XMarkIcon className="h-5 w-5" aria-hidden="true" />,
  UNAVAILABLE: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
}
const repositoryCheckDisplays: Record<RepositoryCheckStatus, { className: string; text: string }> = {
  idle: { className: 'text-blue-700', text: 'Checking Croissant file' },
  CHECKING: { className: 'text-blue-700', text: 'Checking Croissant file' },
  FOUND: { className: 'text-emerald-600', text: 'Croissant file found at repository root' },
  NOT_FOUND: { className: 'text-red-600', text: "Croissant file not found at repository root" },
  UNAVAILABLE: { className: 'text-red-600', text: 'Could not check Croissant file (Your repository may be private)' },
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
  onValidationChange,
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
      : 'CHECKING'
  }
  const statusDisplay = repositoryCheckDisplays[status]

  useEffect(() => {
    onValidationChange?.(status === 'FOUND')
  }, [onValidationChange, status])

  useEffect(() => {
    if (!canCheckRepositoryUrl) {
      return
    }

    const controller = new AbortController()
    let retryCount = 0
    let timer: ReturnType<typeof setTimeout>

    async function checkRepository() {
      try {
        const response = await checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet({
          query: { repository_url: repositoryUrl },
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        const result = response.data
        const transient = !result || result.reason_code === 'REMOTE_TEMPORARY'
        if (transient && retryCount < 2) {
          retryCount += 1
          timer = setTimeout(() => void checkRepository(), retryCount * 1000)
          return
        }
        setCompletedCheck({
          checkMode, repositoryUrl,
          status: result?.status ?? 'UNAVAILABLE',
          message: result?.message ?? 'Could not check the repository. Edit the URL to try again.',
        })
      } catch {
        if (controller.signal.aborted) return
        if (retryCount < 2) {
          retryCount += 1
          timer = setTimeout(() => void checkRepository(), retryCount * 1000)
          return
        }
        setCompletedCheck({ checkMode, repositoryUrl, status: 'UNAVAILABLE', message: 'Could not reach the server. Edit the URL to try again.' })
      }
    }
    timer = setTimeout(() => void checkRepository(), 500)
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
        aria-invalid={canCheckRepositoryUrl && (status === 'NOT_FOUND' || status === 'UNAVAILABLE')}
        maxLength={maxLength}
        onChange={(event) => {
          setCompletedCheck(null)
          onValidationChange?.(false)
          onChange(event.target.value)
        }}
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
          {status === 'UNAVAILABLE' ? completedCheck?.message ?? statusDisplay.text : statusDisplay.text}
        </span>
      ) : null}
    </label>
  )
}
