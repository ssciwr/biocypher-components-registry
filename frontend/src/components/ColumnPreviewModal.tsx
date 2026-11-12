import { useEffect, useState } from 'react'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { getAdapterMetadataApiV1AdaptersAdapterIdMetadataGet, type AdapterDataSourceResponse } from '../api/client'
import GenericModal from './GenericModal'
import { readDatasetColumns, type DatasetColumn } from './columnPreview'

type ColumnPreviewModalProps = Readonly<{
  adapterId: string
  source: AdapterDataSourceResponse
  open?: boolean
  onClose?: () => void
}>

function ColumnPreviewModal({ open, ...props }: ColumnPreviewModalProps) {
  return open ? <ColumnPreviewDialog key={`${props.adapterId}/${props.source.name}`} {...props} /> : null
}

function ColumnPreviewDialog({ adapterId, source, onClose }: Omit<ColumnPreviewModalProps, 'open'>) {
  const [columns, setColumns] = useState<DatasetColumn[] | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    void getAdapterMetadataApiV1AdaptersAdapterIdMetadataGet({
      path: { adapter_id: adapterId },
      signal: AbortSignal.timeout(5000),
    })
      .then(({ data }) => setColumns(data?.metadata ? readDatasetColumns(data.metadata, source.name) : []))
      .catch(() => setColumns([]))
  }, [adapterId, source.name])

  const searchTerm = query.replace(/\s/g, '').toLowerCase()
  const matchingColumns = columns?.filter((column) => (
    Object.values(column).join('').replace(/\s/g, '').toLowerCase().includes(searchTerm)
  )) ?? []
  const columnCount = columns?.length ?? source.column_count ?? 0
  const title = `Data Source "${source.name}" - ${columnCount} ${columnCount === 1 ? 'Column' : 'Columns'}`

  return (
    <GenericModal
      open
      onClose={onClose}
      title={title}
      panelClassName="flex max-h-full w-full max-w-[96rem] flex-col rounded-3xl border border-slate-200 bg-white p-5 text-left shadow-xl sm:p-8"
      closeButtonClassName="bg-blue-600 text-white hover:bg-blue-700"
      headerContent={(
        <label className="order-last flex w-full min-w-0 items-center gap-2 rounded-2xl border border-slate-200 px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500 md:order-none md:ml-auto md:w-80 lg:w-96">
          <MagnifyingGlassIcon className="h-5 w-5 flex-none text-slate-300" aria-hidden="true" />
          <input
            aria-label="Search columns"
            className="min-w-0 w-full bg-transparent text-base text-slate-700 outline-none placeholder:text-slate-500"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search columns..."
            type="search"
            value={query}
          />
        </label>
      )}
      contentClassName="mt-6 min-h-0 overflow-auto rounded-t-xl border border-slate-200 bg-slate-100/80 text-sm text-slate-950"
      content={(
        <table aria-busy={columns === null} className="w-full min-w-[48rem] table-fixed border-collapse text-left">
          <caption className="sr-only">Column names, data types, examples, and descriptions for {source.name}</caption>
          <thead className="sticky top-0 bg-slate-100 text-slate-500">
            <tr>
              <th className="w-[15%] px-5 py-3 font-medium" scope="col">Field name</th>
              <th className="w-[10%] px-5 py-3 font-medium" scope="col">Data type</th>
              <th className="w-1/4 px-5 py-3 font-medium" scope="col">Example</th>
              <th className="w-1/2 px-5 py-3 font-medium" scope="col">Description</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 border-t border-slate-200">
            {matchingColumns.map((column, index) => (
              <tr className="align-top" key={`${column.name}/${index}`}>
                <th className="break-words px-5 py-4 font-mono font-normal" scope="row">{column.name}</th>
                <td className="break-words px-5 py-4">{column.dataType || 'Not provided'}</td>
                <td className="whitespace-pre-wrap break-words px-5 py-4">{column.examples || 'Not provided'}</td>
                <td className="break-words px-5 py-4">{column.description || 'Not provided'}</td>
              </tr>
            ))}
            {columns !== null && matchingColumns.length === 0 ? (
              <tr><td className="px-5 py-6 text-slate-600" colSpan={4} role="status">
                {columns.length ? 'No columns match your search.' : 'Service not available presently, sorry. Please try again later.'}
              </td></tr>
            ) : null}
          </tbody>
        </table>
      )}
    />
  )
}

export default ColumnPreviewModal
