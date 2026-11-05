import type { AdapterMaintainerResponse } from '../api/client'

function MaintainerAvatar({ maintainer, showName = false }: Readonly<{ maintainer?: AdapterMaintainerResponse | null; showName?: boolean }>) {
  if (!maintainer) return <span className="text-sm text-slate-500">No maintainer avatar available</span>

  const displayName = maintainer.username.trim() || 'Unknown maintainer'
  const profileUrl = maintainer.profile_url ?? null
  const fallbackLabel = displayName.slice(0, 2).toUpperCase()

  return (
    <span className="flex items-center gap-3">
      {maintainer.avatar_url ? (
        <img alt={displayName} className="h-10 w-10 rounded-full border border-slate-200" src={maintainer.avatar_url} />
      ) : (
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-sm font-semibold text-slate-700" aria-hidden="true">
          {fallbackLabel}
        </span>
      )}
      {showName ? (
        <span>
          {profileUrl ? (
            <a className="block text-sm font-medium text-slate-950 hover:text-blue-700" href={profileUrl} rel="noreferrer" target="_blank">
              {displayName}
            </a>
          ) : (
            <span className="block text-sm font-medium text-slate-950">{displayName}</span>
          )}
        </span>
      ) : null}
    </span>
  )
}

export default MaintainerAvatar
