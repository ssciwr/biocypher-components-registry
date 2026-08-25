import { ArrowRightOnRectangleIcon, SparklesIcon } from '@heroicons/react/24/outline'
import bioCypherLogo from '../assets/logo-biocypher.png'
import { client } from '../api/client/client.gen'

type AuthUser = Readonly<{
  authenticated: boolean
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
          <span className="text-sm text-slate-500">| Registry</span>
        </a>
        <nav className="hidden items-center gap-16 text-sm text-slate-600 md:flex" aria-label="Main">
          <a className="hover:text-slate-950" href="/adapters">
            Explore
          </a>
          <a className="hover:text-slate-950" href="/register">
            Register
          </a>
        </nav>
        <div className="flex items-center gap-3">
          {authUser ? (
            <span className="hidden items-center gap-2 sm:inline-flex">
              <button
                aria-label="Sign out of GitHub"
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-blue-200 hover:text-blue-600"
                onClick={() => void onLogout()}
                title="Sign out"
                type="button"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5" aria-hidden="true" />
                Sign out
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
          <a
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-base text-white hover:bg-blue-700"
            href="/workspace"
          >
            <SparklesIcon className="h-5 w-5" aria-hidden="true" />
            <b>MCP Workspace</b>
          </a>
        </div>
      </div>
    </header>
  )
}

export type { AuthUser }
export default AppHeader
