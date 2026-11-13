const MAX_BIBTEX_BYTES = 1024 * 1024

export async function citationTextFromBibtexFile(file: File): Promise<string> {
  if (!file.name.toLowerCase().endsWith('.bib')) {
    throw new Error('Select a BibTeX file with the .bib extension.')
  }
  if (file.size > MAX_BIBTEX_BYTES) {
    throw new Error('The BibTeX file must not exceed 1 MiB.')
  }

  let text: string
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()).trim()
  } catch {
    throw new Error('The BibTeX file must use UTF-8 encoding.')
  }
  if (!/^@[a-z]+\s*[({]/i.test(text)) {
    throw new Error('The selected file does not contain a BibTeX entry.')
  }
  return text
}
