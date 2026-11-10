import type { DatasetSourceSelection } from './types'

export function selectionFromFile(file: File): DatasetSourceSelection {
  return {
    entries: [{ file, relativePath: file.name }],
    kind: 'file',
    name: file.name,
  }
}

export function selectionFromFolderFiles(files: FileList): DatasetSourceSelection {
  const selected = Array.from(files)
  if (!selected.length) throw new Error('The selected folder is empty.')

  const firstPath = selected[0].webkitRelativePath
  const rootName = firstPath.split('/')[0]
  if (!rootName) {
    throw new Error('The browser did not provide the selected folder path.')
  }

  return {
    entries: selected.map((file) => ({
      file,
      relativePath: stripRoot(file.webkitRelativePath, rootName),
    })),
    kind: 'folder',
    name: rootName,
  }
}

function stripRoot(path: string, expectedRoot: string): string {
  const [root, ...relativeParts] = path.split('/')
  if (root !== expectedRoot || !relativeParts.length) {
    throw new Error('The folder selection contains inconsistent paths.')
  }
  return relativeParts.join('/')
}
