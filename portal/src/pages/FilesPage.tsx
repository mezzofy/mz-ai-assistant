import React, { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { portalApi } from '../api/portal'
import type { FileRecord, FolderGroup } from '../types'

const FILE_ICONS: Record<string, string> = {
  pdf: '\uD83D\uDCC4', xlsx: '\uD83D\uDCCA', xls: '\uD83D\uDCCA', csv: '\uD83D\uDCCA',
  docx: '\uD83D\uDCDD', doc: '\uD83D\uDCDD', pptx: '\uD83D\uDCBD', ppt: '\uD83D\uDCBD',
  image: '\uD83D\uDDBC', png: '\uD83D\uDDBC', jpg: '\uD83D\uDDBC', jpeg: '\uD83D\uDDBC',
  mp4: '\uD83C\uDFAC', mp3: '\uD83C\uDFB5', default: '\uD83D\uDCC1',
}

function fileIcon(type: string) {
  return FILE_ICONS[type?.toLowerCase()] || FILE_ICONS.default
}

function formatBytes(bytes: number | null) {
  if (!bytes) return '\u2014'
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function folderLabel(g: FolderGroup) {
  return [g.scope, g.department].filter(Boolean).join(' / ').toUpperCase()
}

const DEPT_ORDER = ['company', 'management', 'finance', 'hr', 'sales', 'marketing', 'support']

interface FlatFile extends FileRecord {
  folderLabel: string
}

export default function FilesPage() {
  const qc = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<FileRecord | null>(null)
  const [renamingFile, setRenamingFile] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [uploadDept, setUploadDept] = useState('')
  const [uploadScope, setUploadScope] = useState('shared')
  const [showUpload, setShowUpload] = useState(false)
  const uploadRef = useRef<HTMLInputElement>(null)

  const { data: folderData } = useQuery({
    queryKey: ['folder-tree'],
    queryFn: () => portalApi.getFolderTree().then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => portalApi.deleteFile(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folder-tree'] })
      setConfirmDelete(null)
    },
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => portalApi.renameFile(id, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['folder-tree'] })
      setRenamingFile(null)
    },
  })

  const folders: FolderGroup[] = (folderData?.folders || [])
    .filter((g: FolderGroup) => g.scope !== 'personal')
    .sort((a: FolderGroup, b: FolderGroup) => {
      if (a.scope === 'company' && b.scope !== 'company') return -1
      if (b.scope === 'company' && a.scope !== 'company') return 1
      const ai = DEPT_ORDER.indexOf((a.department || '').toLowerCase())
      const bi = DEPT_ORDER.indexOf((b.department || '').toLowerCase())
      if (ai === -1 && bi === -1) return 0
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })

  const allFiles: FlatFile[] = folders.flatMap((g) =>
    g.files.map((f) => ({ ...f, folderLabel: folderLabel(g) }))
  )

  const displayed: FlatFile[] = searchQuery.trim()
    ? allFiles.filter((f) =>
        f.filename.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : allFiles

  const handleRename = (file: FileRecord) => {
    setRenamingFile(file.id)
    setRenameValue(file.filename)
  }

  const submitRename = (id: string) => {
    if (renameValue.trim()) {
      renameMutation.mutate({ id, name: renameValue.trim() })
    } else {
      setRenamingFile(null)
    }
  }

  const handleUploadFile = async (file: File) => {
    try {
      await portalApi.uploadFile(file, uploadDept || undefined, uploadScope)
      qc.invalidateQueries({ queryKey: ['folder-tree'] })
      setShowUpload(false)
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-white flex-shrink-0" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
          Files
        </h1>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search files..."
          className="flex-1 px-3 py-1.5 rounded-lg text-sm text-white border outline-none transition-colors focus:border-orange-500"
          style={{ background: '#1E2A3A', borderColor: '#374151' }}
        />
        <button
          onClick={() => setShowUpload(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all flex-shrink-0"
          style={{ background: '#f97316' }}
        >
          + Upload File
        </button>
      </div>

      {/* File Count */}
      <div className="text-xs" style={{ color: '#6B7280' }}>
        {searchQuery.trim()
          ? `${displayed.length} result${displayed.length !== 1 ? 's' : ''} for "${searchQuery}"`
          : `${allFiles.length} file${allFiles.length !== 1 ? 's' : ''} total`}
      </div>

      {/* Files Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        {displayed.length === 0 ? (
          <div className="py-12 text-center text-xs" style={{ color: '#6B7280' }}>
            {searchQuery.trim() ? 'No files match your search.' : 'No files.'}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid #1E2A3A', background: '#0F1F35' }}>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>
                  Folder
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>
                  Size
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>
                  Date
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: '#6B7280' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((f) => (
                <tr key={f.id} className="border-t hover:bg-white/5 transition-colors" style={{ borderColor: '#1E2A3A' }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span>{fileIcon(f.file_type)}</span>
                      {renamingFile === f.id ? (
                        <input
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => submitRename(f.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') submitRename(f.id)
                            if (e.key === 'Escape') setRenamingFile(null)
                          }}
                          autoFocus
                          className="px-1 py-0.5 rounded text-sm text-white border outline-none"
                          style={{ background: '#1E2A3A', borderColor: '#374151', width: '220px' }}
                        />
                      ) : (
                        <span className="text-gray-200 truncate max-w-[260px]">{f.filename}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-mono font-medium"
                      style={{ background: '#1E2A3A', color: '#f97316' }}
                    >
                      {f.folderLabel}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs font-mono" style={{ color: '#6B7280' }}>
                    {formatBytes(f.size_bytes)}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#6B7280' }}>
                    {f.created_at ? new Date(f.created_at).toLocaleDateString() : '\u2014'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 justify-end">
                      <a
                        href={f.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2 py-1 rounded text-xs transition-colors"
                        style={{ color: '#f97316' }}
                      >
                        Download
                      </a>
                      <button
                        onClick={() => handleRename(f)}
                        className="px-2 py-1 rounded text-xs transition-colors"
                        style={{ color: '#4DA6FF' }}
                      >
                        Rename
                      </button>
                      <button
                        onClick={() => setConfirmDelete(f)}
                        className="px-2 py-1 rounded text-xs transition-colors hover:bg-red-500/10"
                        style={{ color: '#EF4444' }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Upload Modal */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="w-full max-w-sm p-6 rounded-xl border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
            <h3 className="text-base font-semibold text-white mb-4">Upload File</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Department (optional)</label>
                <input
                  type="text"
                  value={uploadDept}
                  onChange={(e) => setUploadDept(e.target.value)}
                  placeholder="e.g. finance"
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Scope</label>
                <select
                  value={uploadScope}
                  onChange={(e) => setUploadScope(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none"
                  style={{ background: '#1E2A3A', borderColor: '#374151' }}
                >
                  <option value="shared">shared</option>
                  <option value="personal">personal</option>
                  <option value="department">department</option>
                </select>
              </div>
              <div>
                <input
                  type="file"
                  ref={uploadRef}
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) handleUploadFile(file)
                    e.target.value = ''
                  }}
                />
                <button
                  onClick={() => uploadRef.current?.click()}
                  className="w-full py-2 rounded-lg text-sm font-medium text-white transition-all"
                  style={{ background: '#f97316' }}
                >
                  Choose File & Upload
                </button>
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowUpload(false)}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

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
