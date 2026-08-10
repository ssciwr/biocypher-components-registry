import { ArrowRightOnRectangleIcon, SparklesIcon } from '@heroicons/react/24/outline'
import bioCypherLogo from '../assets/logo-biocypher.png'
import { client } from '../api/client/client.gen'

type AuthUser = Readonly<{
  github_login: string
}>

type AppHeaderProps = Readonly<{
  authUser: AuthUser | null
  onLogout: () => Promise<void>
}>

function AppHeader({ authUser, onLogout }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <a className="flex items-center gap-2" href="/">
          <img alt="BioCypher" className="h-7 w-7" src={bioCypherLogo} />
          <span className="text-base font-semibold">BioCypher</span>
          <span className="hidden text-sm text-slate-500 sm:inline">| Registry</span>
        </a>
        <nav className="hidden items-center gap-16 text-sm text-slate-600 md:flex" aria-label="Main">
          <a className="hover:text-slate-950" href="/adapters">
            Explore
          </a>
          <a className="hover:text-slate-950" href="/create">
            Create
          </a>
          <a className="hover:text-slate-950" href="/register">
            Register
          </a>
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          {authUser ? (
            <span className="hidden items-center gap-2 sm:inline-flex">
              <span className="rounded-full border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700">
                {authUser.github_login}
              </span>
              <button
                aria-label="Sign out of GitHub"
                className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-slate-200 text-slate-500 hover:border-blue-200 hover:text-blue-600"
                onClick={() => void onLogout()}
                title="Sign out"
                type="button"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </span>
          ) : (
            <a
              className="hidden cursor-pointer rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-blue-200 hover:text-blue-600 sm:inline-flex"
              href={client.buildUrl({ url: '/api/v1/auth/github/start' })}
            >
              Sign in with GitHub
            </a>
          )}
          <button
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg bg-slate-300 px-5 py-3 text-base text-white"
            disabled
            type="button"
          >
            <SparklesIcon className="h-5 w-5" aria-hidden="true" />
            <b>MCP Workspace</b>
          </button>
        </div>
      </div>
    </header>
  )
}

export type { AuthUser }
export default AppHeader
