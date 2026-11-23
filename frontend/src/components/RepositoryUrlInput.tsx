import { useEffect, useState, type ReactNode } from 'react'
import { CheckIcon, ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet } from '../api/client'

type RepositoryCheckStatus = 'idle' | 'checking' | 'found' | 'missing' | 'blocked' | 'unavailable'
type RepositoryCheckMode = 'croissant-file' | 'none'
type CompletedRepositoryCheckStatus = Exclude<RepositoryCheckStatus, 'idle' | 'checking'>

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
  unavailable: <ExclamationTriangleIcon className="h-5 w-5" aria-hidden="true" />,
}
const repositoryCheckDisplays: Record<RepositoryCheckStatus, { className: string; text: string }> = {
  idle: { className: 'text-blue-700', text: 'Checking Croissant file' },
  checking: { className: 'text-blue-700', text: 'Checking Croissant file' },
  found: { className: 'text-emerald-600', text: 'Croissant file found at repository root' },
  missing: { className: 'text-red-600', text: "Croissant file not found at this repository link's root (Your repository may be private)" },
  blocked: { className: 'text-red-600', text: 'Enter the source code repository URL for this adapter.' },
  unavailable: { className: 'text-red-600', text: 'Unable to connect to service' },
}

/*
 * AI-Generated.
 * Exclude registry pages whose HTML fallback can appear to be a metadata file.
 */
function isRegistryPageUrl(repositoryUrl: string): boolean {
  if (!URL.canParse(repositoryUrl)) return false
  const repositoryAddress = new URL(repositoryUrl)
  return repositoryAddress.origin === globalThis.location.origin || repositoryAddress.hostname === 'registry.biocypher.org'
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
  const showRepositoryFeedback = hasEditedRepository || showValidationFeedback
  let status: RepositoryCheckStatus = isRegistryPage ? 'blocked' : 'idle'
  if (canCheckRepositoryUrl) {
    status = completedCheck?.repositoryUrl === repositoryUrl
      ? completedCheck.status
      : 'checking'
  }
  const statusDisplay = repositoryCheckDisplays[status]

  useEffect(() => {
    onValidatedRepositoryChange?.(status === 'found' ? repositoryUrl : null)
  }, [onValidatedRepositoryChange, repositoryUrl, status])

  useEffect(() => {
    if (!canCheckRepositoryUrl) {
      return
    }

    const controller = new AbortController()

    void checkRegistrationCroissantFilePresenceApiV1RegistrationsCroissantFilePresentCheckGet({
      query: { repository_url: repositoryUrl },
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]),
    })
      .then((metadataResult) => {
        if (controller.signal.aborted) return
        if (metadataResult.response?.status !== 200 || metadataResult.error || typeof metadataResult.data?.has_croissant_file !== 'boolean') {
          const invalidRepository = metadataResult.response?.status === 400 || metadataResult.response?.status === 422
          setCompletedCheck({ repositoryUrl, status: invalidRepository ? 'blocked' : 'unavailable' })
          return
        }
        const checkStatus = metadataResult.data.has_croissant_file === true ? 'found' : 'missing'
        setCompletedCheck({ repositoryUrl, status: checkStatus })
      })
      .catch(() => {
        if (!controller.signal.aborted) setCompletedCheck({ repositoryUrl, status: 'unavailable' })
      })

    return () => controller.abort()
  }, [canCheckRepositoryUrl, repositoryUrl])

  return (
    <label className={labelClassName}>
      <span>{label}</span>
      <input
        className={inputClassName}
        aria-invalid={showRepositoryFeedback && (status === 'missing' || status === 'blocked')}
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
          {statusDisplay.text}
        </span>
      ) : null}
    </label>
  )
}
