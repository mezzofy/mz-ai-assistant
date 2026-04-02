import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Building2, FolderOpen } from 'lucide-react'
import { portalApi } from '../api/portal'
import type { FileRecord, FolderRecord } from '../types'

// ── Helpers ───────────────────────────────────────────────────────────────────

function FileTypeAvatar({ type }: { type: string }) {
  const label = (type || 'file').slice(0, 3).toUpperCase()
  return (
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
      style={{ background: '#1E2A3A', color: '#f97316' }}
    >
      {label}
    </div>
  )
}

function formatBytes(bytes: number | null) {
  if (!bytes) return '\u2014'
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function extractFiles(res: { data: unknown }): FileRecord[] {
  const d = res.data
  if (Array.isArray(d)) return d as FileRecord[]
  if (d && typeof d === 'object') {
    const obj = d as Record<string, unknown>
    if (Array.isArray(obj.data)) return obj.data as FileRecord[]
    if (Array.isArray(obj.files)) return obj.files as FileRecord[]
  }
  return []
}

function extractFolders(res: { data: unknown }): FolderRecord[] {
  const d = res.data
  if (Array.isArray(d)) return d as FolderRecord[]
  if (d && typeof d === 'object' && Array.isArray((d as { folders?: unknown }).folders))
    return (d as { folders: FolderRecord[] }).folders
  return []
}

// ── Types ─────────────────────────────────────────────────────────────────────

type ScopeKey = 'company' | 'department'

type NavView =
  | { type: 'root' }
  | { type: 'scope'; scope: ScopeKey; label: string }
  | { type: 'folder'; scope: ScopeKey; folder: FolderRecord }

interface Props {
  department: string
  sectionTitle: string
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function DeptFilesPage({ department, sectionTitle }: Props) {
  const [view, setView] = useState<NavView>({ type: 'root' })
  const [folders, setFolders] = useState<FolderRecord[]>([])
  const [files, setFiles] = useState<FileRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Upload state
  const [showUpload, setShowUpload] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  // New folder state
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [folderError, setFolderError] = useState<string | null>(null)

  // Root-level counts (for folder cards)
  const [companyCounts, setCompanyCounts] = useState({ files: 0, folders: 0 })
  const [deptCounts, setDeptCounts] = useState({ files: 0, folders: 0 })

  // Load root-level counts on mount
  useEffect(() => {
    Promise.all([
      portalApi.getDeptFiles('company'),
      portalApi.getDeptFiles('department', department),
      portalApi.getDeptFolders('company'),
      portalApi.getDeptFolders('department'),
    ]).then(([cf, df, cfo, dfo]) => {
      setCompanyCounts({ files: extractFiles(cf).length, folders: extractFolders(cfo).length })
      setDeptCounts({ files: extractFiles(df).length, folders: extractFolders(dfo).length })
    }).catch(() => {/* silently ignore count load errors */})
  }, [department])

  const loadView = useCallback((v: NavView) => {
    setView(v)
    setSearchQuery('')
    setError(null)
    if (v.type === 'root') return

    setLoading(true)
    if (v.type === 'scope') {
      const dept = v.scope === 'department' ? department : undefined
      Promise.all([
        portalApi.getDeptFolders(v.scope, dept),
        portalApi.getDeptFiles(v.scope, dept),
      ])
        .then(([fRes, fileRes]) => {
          setFolders(extractFolders(fRes))
          setFiles(extractFiles(fileRes))
        })
        .catch(() => setError('Failed to load contents.'))
        .finally(() => setLoading(false))
    } else if (v.type === 'folder') {
      const dept = v.scope === 'department' ? department : undefined
      portalApi.getDeptFiles(v.scope, dept, v.folder.id)
        .then((res) => setFiles(extractFiles(res)))
        .catch(() => setError('Failed to load folder contents.'))
        .finally(() => setLoading(false))
    }
  }, [department])

  const handleCreateFolder = async () => {
    if (!newFolderName.trim() || view.type !== 'scope') return
    setCreatingFolder(true)
    setFolderError(null)
    try {
      await portalApi.createDeptFolder(newFolderName.trim(), view.scope)
      setNewFolderName('')
      setShowNewFolder(false)
      loadView(view) // refresh
    } catch {
      setFolderError('Failed to create folder.')
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    const folderId = view.type === 'folder' ? view.folder.id : undefined
    try {
      await portalApi.uploadDeptFile(file, folderId)
      setShowUpload(false)
      loadView(view) // refresh
      // refresh root counts
      Promise.all([
        portalApi.getDeptFiles('department', department),
      ]).then(([df]) => setDeptCounts((c) => ({ ...c, files: extractFiles(df).length })))
    } catch {
      setUploadError('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const displayed = searchQuery.trim()
    ? files.filter((f) => f.filename.toLowerCase().includes(searchQuery.toLowerCase()))
    : files

  const canUpload = view.type === 'scope'
    ? view.scope === 'department'
    : view.type === 'folder'
    ? view.scope === 'department'
    : false

  const canCreateFolder = view.type === 'scope' && view.scope === 'department'

  // ── Root view ────────────────────────────────────────────────────────────────

  if (view.type === 'root') {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>Files</h1>
          <p className="text-xs mt-1" style={{ color: '#6B7280' }}>Browse company and department folders</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {/* Company Folder Card */}
          <button
            onClick={() => loadView({ type: 'scope', scope: 'company', label: 'Company' })}
            className="text-left p-5 rounded-xl border transition-all hover:bg-white/5"
            style={{ background: '#111827', borderColor: '#1E2A3A' }}
          >
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg flex-shrink-0" style={{ background: '#1E2A3A' }}>
                <Building2 size={28} style={{ color: '#f97316' }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-white">Company</div>
                <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
                  Shared company files
                </div>
                <div className="flex gap-3 mt-2">
                  <span className="text-xs" style={{ color: '#f97316' }}>
                    {companyCounts.folders} folder{companyCounts.folders !== 1 ? 's' : ''}
                  </span>
                  <span className="text-xs" style={{ color: '#6B7280' }}>
                    {companyCounts.files} file{companyCounts.files !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </div>
          </button>

          {/* Department Folder Card */}
          <button
            onClick={() => loadView({ type: 'scope', scope: 'department', label: sectionTitle })}
            className="text-left p-5 rounded-xl border transition-all hover:bg-white/5"
            style={{ background: '#111827', borderColor: '#1E2A3A' }}
          >
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-lg flex-shrink-0" style={{ background: '#1E2A3A' }}>
                <FolderOpen size={28} style={{ color: '#f97316' }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-white">{sectionTitle}</div>
                <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
                  {sectionTitle} department files
                </div>
                <div className="flex gap-3 mt-2">
                  <span className="text-xs" style={{ color: '#f97316' }}>
                    {deptCounts.folders} folder{deptCounts.folders !== 1 ? 's' : ''}
                  </span>
                  <span className="text-xs" style={{ color: '#6B7280' }}>
                    {deptCounts.files} file{deptCounts.files !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </div>
          </button>
        </div>
      </div>
    )
  }

  // ── Scope / Folder view ───────────────────────────────────────────────────────

  const scopeLabel = view.type === 'scope' ? view.label : view.type === 'folder' ? (view.scope === 'company' ? 'Company' : sectionTitle) : ''
  const folderName = view.type === 'folder' ? view.folder.name : null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Breadcrumb */}
          <button
            onClick={() => loadView({ type: 'root' })}
            className="text-sm hover:text-white transition-colors"
            style={{ color: '#6B7280' }}
          >
            Files
          </button>
          <span style={{ color: '#374151' }}>/</span>
          {folderName ? (
            <>
              <button
                onClick={() => loadView({
                  type: 'scope',
                  scope: view.type === 'folder' ? view.scope : 'department',
                  label: scopeLabel,
                })}
                className="text-sm hover:text-white transition-colors"
                style={{ color: '#6B7280' }}
              >
                {scopeLabel}
              </button>
              <span style={{ color: '#374151' }}>/</span>
              <span className="text-sm font-medium text-white">{folderName}</span>
            </>
          ) : (
            <span className="text-sm font-medium text-white">{scopeLabel}</span>
          )}
          <span className="text-xs ml-1" style={{ color: '#6B7280' }}>
            {loading ? '' : `${displayed.length} file${displayed.length !== 1 ? 's' : ''}`}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {canCreateFolder && (
            <button
              onClick={() => { setShowNewFolder(true); setFolderError(null); setNewFolderName('') }}
              className="px-3 py-2 rounded-lg text-xs font-medium text-white border transition-all"
              style={{ background: '#1E2A3A', borderColor: '#374151' }}
            >
              + New Folder
            </button>
          )}
          {canUpload && (
            <button
              onClick={() => { setShowUpload(true); setUploadError(null) }}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all flex-shrink-0"
              style={{ background: '#f97316' }}
            >
              + Upload File
            </button>
          )}
        </div>
      </div>

      {/* New Folder inline form */}
      {showNewFolder && (
        <div className="flex items-center gap-2 p-3 rounded-lg border" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreateFolder(); if (e.key === 'Escape') setShowNewFolder(false) }}
            placeholder="Folder name..."
            autoFocus
            className="flex-1 bg-transparent text-sm text-white outline-none"
            style={{ color: 'white' }}
          />
          {folderError && <span className="text-xs text-red-400">{folderError}</span>}
          <button
            onClick={handleCreateFolder}
            disabled={creatingFolder || !newFolderName.trim()}
            className="px-3 py-1 rounded text-xs font-medium text-white"
            style={{ background: creatingFolder || !newFolderName.trim() ? '#374151' : '#f97316' }}
          >
            {creatingFolder ? 'Creating...' : 'Create'}
          </button>
          <button
            onClick={() => setShowNewFolder(false)}
            className="px-3 py-1 rounded text-xs text-gray-400 hover:text-white"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Folder list (only in scope view) */}
      {view.type === 'scope' && !loading && folders.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#4B5563' }}>
            Folders
          </div>
          <div className="grid grid-cols-2 gap-2">
            {folders.map((folder) => (
              <button
                key={folder.id}
                onClick={() => loadView({ type: 'folder', scope: view.scope, folder })}
                className="flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left transition-all hover:bg-white/5"
                style={{ background: '#111827', borderColor: '#1E2A3A' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#f97316" stroke="#f97316" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span className="text-sm text-white truncate">{folder.name}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2" className="ml-auto flex-shrink-0">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Files section label */}
      {view.type === 'scope' && !loading && (files.length > 0 || folders.length > 0) && (
        <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#4B5563' }}>
          Files
        </div>
      )}

      {/* Search bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search files..."
          className="flex-1 px-3 py-2 rounded-lg text-sm text-white border outline-none transition-colors focus:border-orange-500"
          style={{ background: '#111827', borderColor: '#1E2A3A' }}
        />
        {searchQuery.trim() && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="px-4 py-2 rounded-lg text-sm"
            style={{ background: '#1E2A3A', color: '#6B7280' }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Files Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: '#111827', borderColor: '#1E2A3A' }}>
        {loading ? (
          <div className="py-12 text-center text-xs" style={{ color: '#6B7280' }}>Loading...</div>
        ) : error ? (
          <div className="py-12 text-center text-xs text-red-400">{error}</div>
        ) : displayed.length === 0 ? (
          <div className="py-12 text-center text-xs" style={{ color: '#6B7280' }}>
            {searchQuery.trim() ? 'No files match your search.' : 'No files.'}
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left" style={{ color: '#6B7280', borderColor: '#1E2A3A' }}>
                <th className="px-4 py-3">Name</th>
                <th className="py-3">Size</th>
                <th className="py-3">Date</th>
                <th className="py-3 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((f) => (
                <tr key={f.id} className="border-t hover:bg-white/5 transition-colors" style={{ borderColor: '#1E2A3A' }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileTypeAvatar type={f.file_type} />
                      <span className="text-gray-200 truncate max-w-[260px]">{f.filename}</span>
                    </div>
                  </td>
                  <td className="py-3 font-mono" style={{ color: '#6B7280' }}>{formatBytes(f.size_bytes)}</td>
                  <td className="py-3" style={{ color: '#6B7280' }}>
                    {f.created_at ? new Date(f.created_at).toLocaleDateString() : '\u2014'}
                  </td>
                  <td className="py-3 pr-4">
                    <button
                      onClick={() => portalApi.downloadDeptFile(f.id, f.filename)}
                      title="Download"
                      className="p-1.5 rounded transition-colors hover:bg-orange-500/10"
                      style={{ color: '#f97316' }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                      </svg>
                    </button>
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
            <h3 className="text-base font-semibold text-white mb-1">Upload File</h3>
            <p className="text-xs mb-4" style={{ color: '#6B7280' }}>
              {folderName
                ? <>Uploading to <span style={{ color: '#f97316' }}>{sectionTitle} / {folderName}</span></>
                : <>Uploading to <span style={{ color: '#f97316' }}>{sectionTitle}</span> department folder</>}
            </p>
            <input
              type="file"
              ref={uploadRef}
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleUpload(file)
                e.target.value = ''
              }}
            />
            {uploadError && <p className="text-xs text-red-400 mb-3">{uploadError}</p>}
            <button
              onClick={() => uploadRef.current?.click()}
              disabled={uploading}
              className="w-full py-2 rounded-lg text-sm font-medium text-white transition-all"
              style={{ background: uploading ? '#6B7280' : '#f97316' }}
            >
              {uploading ? 'Uploading...' : 'Choose File & Upload'}
            </button>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowUpload(false)}
                disabled={uploading}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
