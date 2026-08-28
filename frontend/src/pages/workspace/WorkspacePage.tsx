import GenericModal from '../../components/GenericModal'
import {
  ChatPane,
  WorkspaceError,
  WorkspaceTopBar,
} from './WorkspaceDisplayComponents.tsx'
import {
  DirectoryPane,
  EditorPane,
} from './FileEditingAndDirectoryInterfaces'
import { WorkspaceKeyForm } from './WorkspaceKeyForm'
import { useWorkspaceSession } from './useWorkspaceSession'

type WorkspacePageProps = Readonly<{
  signedIn: boolean
  signInUrl: string
}>


/*
Handles setting out the whole interface for running sessions and managing the API key being provided,
and also gates access on the client side unelss the user is signed in to GitHUb.
 */
function WorkspacePage({ signedIn, signInUrl }: WorkspacePageProps) {
  const workspace = useWorkspaceSession({ signedIn })
  const needsKey = Boolean(workspace.session && !workspace.session.hasLLMKey)

  return (
    <section className="relative bg-slate-100">
      <div aria-hidden={!signedIn} className={signedIn ? '' : 'pointer-events-none select-none'}>
        <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-[1600px] flex-col gap-5 px-4 py-5 sm:px-6">
          <WorkspaceTopBar
            onStart={() => void workspace.startSession()}
            pending={workspace.pending}
            session={workspace.session}
          />
          <WorkspaceError error={workspace.error} />
          <div className="grid flex-1 gap-5 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
            <DirectoryPane
              currentDir={workspace.currentDir}
              files={workspace.files}
              onOpenDir={workspace.openDirectory}
              onOpenFile={(entry) => void workspace.openWorkspaceFile(entry)}
              onRefresh={workspace.refreshFiles}
              session={workspace.session}
            />
            <ChatPane
              canSend={workspace.canSend}
              chatEndRef={workspace.chatEndRef}
              messages={workspace.messages}
              onPromptChange={workspace.setPrompt}
              onSend={() => void workspace.sendMessage()}
              onStop={() => void workspace.stopTurn()}
              pending={workspace.pending}
              prompt={workspace.prompt}
              session={workspace.session}
            />
            <EditorPane
              dirtyFile={workspace.dirtyFile}
              onDraftChange={workspace.updateDraft}
              onSave={() => void workspace.saveWorkspaceFile()}
              openFile={workspace.openFile}
              pending={workspace.pending}
            />
          </div>
        </div>
      </div>
      <GenericModal
        content={(
          <WorkspaceKeyForm
            apiKey={workspace.apiKey}
            error={workspace.error}
            onApiKeyChange={workspace.setApiKey}
            onAttachKey={() => void workspace.attachKey()}
            pending={workspace.pending}
          />
        )}
        contentClassName=""
        open={needsKey}
        panelClassName="w-full max-w-5xl rounded-lg border border-slate-200 bg-white p-5 text-left shadow-2xl sm:p-6"
        showTitle={false}
        title="Attach Anthropic API key"
      />
      {!signedIn ? <div className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-200/75" aria-hidden="true" /> : null}
      <GenericModal
        content={(
          <>
            <a
              className="inline-flex h-14 min-w-64 items-center justify-center rounded-lg bg-slate-950 px-8 text-base font-semibold text-white shadow-sm hover:bg-slate-800"
              href={signInUrl}
            >
              Sign in with GitHub
            </a>
            <p className="mx-auto mt-4 max-w-xs text-sm leading-6 text-slate-400">
              and provide a Claude API key to use the MCP Workspace
            </p>
          </>
        )}
        contentClassName="text-center"
        open={!signedIn}
        panelClassName="w-full max-w-md rounded-lg border border-slate-300 bg-white px-8 py-9 text-center shadow-2xl"
        showTitle={false}
        title="Sign in to use the MCP Workspace"
      />
    </section>
  )
}

export default WorkspacePage
