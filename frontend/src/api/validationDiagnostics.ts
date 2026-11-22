import type { ValidationDetailResponse } from './client'

type DiagnosticSource = {
  validation_errors?: string[]
  validation_details?: ValidationDetailResponse[]
}

export function registrationValidationDetails(result: DiagnosticSource | null): ValidationDetailResponse[] {
  const structured = new Map<string, ValidationDetailResponse[]>()
  for (const detail of result?.validation_details ?? []) {
    const key = detail.message.trim()
    if (key) structured.set(key, [...(structured.get(key) ?? []), detail])
  }
  const details: ValidationDetailResponse[] = []
  const seen = new Set<string>()
  function add(detail: ValidationDetailResponse) {
    if (!detail.message.trim()) return
    const key = JSON.stringify([detail.message.trim(), detail.json_path ?? null, detail.requirement ?? null, detail.expected_format ?? null,
      detail.location_description ?? null, detail.source_file ?? null, detail.source_url ?? null,
      detail.line ?? null, detail.column ?? null, detail.location_kind ?? null,
    ])
    if (seen.has(key)) return
    seen.add(key)
    details.push(detail)
  }
  for (const message of result?.validation_errors ?? []) {
    const matches = structured.get(message.trim())
    if (matches) matches.forEach(add)
    else add({ message })
  }
  for (const matches of structured.values()) matches.forEach(add)
  return details
}
