import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { FileRecord } from '../types'

const FILE_ICONS: Record<string, string> = {
  pdf: '📄', xlsx: '📊', xls: '📊', csv: '📊',
  docx: '📝', doc: '📝', pptx: '📽', ppt: '📽',
  image: '🖼', png: '🖼', jpg: '🖼', jpeg: '🖼',
  mp4: '🎬', mp3: '🎵', default: '📁',
}

function fileIcon(type: string) {
  return FILE_ICONS[type?.toLowerCase()] || FILE_ICONS.default
}

function formatBytes(bytes: number | null) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export default function FilesPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [fileType, setFileType] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<FileRecord | null>(null)

  const { data } = useQuery({
    queryKey: ['files', page, fileType],
    queryFn: () => portalApi.getFiles({ page, type: fileType || undefined }).then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => portalApi.deleteFile(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['files'] })
      setConfirmDelete(null)
    },
  })

  const files: FileRecord[] = data?.files || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Files
        </h1>
        <div className="flex gap-2">
          <select
            value={fileType}
            onChange={(e) => { setFileType(e.target.value); setPage(1) }}
            className="px-3 py-1.5 rounded-lg text-sm border outline-none"
            style={{ background: '#111827', borderColor: '#1E2A3A', color: '#E5E7EB' }}
          >
            <option value="">All types</option>
            <option value="pdf">PDF</option>
            <option value="xlsx">Excel</option>
            <option value="docx">Word</option>
            <option value="image">Image</option>
            <option value="csv">CSV</option>
          </select>
        </div>
      </div>

      <div className="rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        <table className="w-full text-xs">
          <thead>
            <tr
              className="border-b text-left"
              style={{ color: '#6B7280', borderColor: '#1E2A3A' }}
            >
              <th className="px-4 py-3">File</th>
              <th className="py-3">Owner</th>
              <th className="py-3">Scope</th>
              <th className="py-3">Size</th>
              <th className="py-3">Uploaded</th>
              <th className="py-3 pr-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.id} className="border-t" style={{ borderColor: '#1E2A3A' }}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span>{fileIcon(f.file_type)}</span>
                    <span className="text-gray-200 truncate max-w-[200px]">{f.filename}</span>
                  </div>
                </td>
                <td className="py-2.5 text-gray-400">{f.owner_email || '—'}</td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded text-xs"
                    style={{ background: '#1E2A3A', color: '#9CA3AF' }}
                  >
                    {f.scope}
                  </span>
                </td>
                <td className="py-2.5 text-gray-400 font-mono">{formatBytes(f.size_bytes)}</td>
                <td className="py-2.5 text-gray-400">
                  {f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2.5 pr-4">
                  <div className="flex gap-2">
                    <a
                      href={f.download_url}
                      className="px-2 py-1 rounded text-xs transition-colors"
                      style={{ color: '#6C63FF' }}
                    >
                      ⬇
                    </a>
                    <button
                      onClick={() => setConfirmDelete(f)}
                      className="px-2 py-1 rounded text-xs transition-colors hover:bg-red-500/10"
                      style={{ color: '#EF4444' }}
                    >
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {files.length === 0 && (
              <tr>
                <td colSpan={6} className="py-12 text-center" style={{ color: '#6B7280' }}>
                  No files
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {data?.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t" style={{ borderColor: '#1E2A3A' }}>
            <div className="text-xs" style={{ color: '#6B7280' }}>
              {data.total} files · Page {page} of {data.pages}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded text-xs transition-colors disabled:opacity-40"
                style={{ background: '#1E2A3A', color: '#E5E7EB' }}
              >
                ‹ Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className="px-3 py-1 rounded text-xs transition-colors disabled:opacity-40"
                style={{ background: '#1E2A3A', color: '#E5E7EB' }}
              >
                Next ›
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Delete Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="w-full max-w-sm p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <h3 className="text-base font-semibold text-white mb-2">Delete File</h3>
            <p className="text-sm mb-5" style={{ color: '#6B7280' }}>
              Permanently delete <span className="text-gray-200">{confirmDelete.filename}</span>? This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(confirmDelete.id)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
                style={{ background: '#EF4444' }}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
