import React, { useState, useEffect, useRef, useCallback } from 'react'
import { portalApi } from '../api/portal'
import type { FileRecord } from '../types'

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

interface FlatFile extends FileRecord {
  folderLabel: string
}

interface Props {
  department: string
  sectionTitle: string
}

export default function DeptFilesPage({ department, sectionTitle }: Props) {
  const [allFiles, setAllFiles] = useState<FlatFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  const loadFiles = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      portalApi.getDeptFiles('company'),
      portalApi.getDeptFiles('department', department),
    ])
      .then(([companyRes, deptRes]) => {
        const extractFiles = (res: { data: unknown }): FileRecord[] => {
          const d = res.data
          if (Array.isArray(d)) return d as FileRecord[]
          if (d && typeof d === 'object' && Array.isArray((d as { data?: unknown }).data))
            return (d as { data: FileRecord[] }).data
          return []
        }
        const companyFiles: FlatFile[] = extractFiles(companyRes).map((f) => ({
          ...f,
          folderLabel: 'COMPANY',
        }))
        const deptFiles: FlatFile[] = extractFiles(deptRes).map((f) => ({
          ...f,
          folderLabel: sectionTitle.toUpperCase(),
        }))
        setAllFiles([...companyFiles, ...deptFiles])
      })
      .catch(() => setError('Failed to load files. Please try again.'))
      .finally(() => setLoading(false))
  }, [department, sectionTitle])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  const handleUploadFile = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      await portalApi.uploadDeptFile(file)
      setShowUpload(false)
      loadFiles()
    } catch {
      setUploadError('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const displayed = searchQuery.trim()
    ? allFiles.filter((f) => f.filename.toLowerCase().includes(searchQuery.toLowerCase()))
    : allFiles

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white flex-shrink-0" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Files
          </h1>
          <span className="text-sm" style={{ color: '#6B7280' }}>
            {loading
              ? 'Loading...'
              : searchQuery.trim()
              ? `${displayed.length} result${displayed.length !== 1 ? 's' : ''}`
              : `${allFiles.length} file${allFiles.length !== 1 ? 's' : ''}`}
          </span>
        </div>
        <button
          onClick={() => { setShowUpload(true); setUploadError(null) }}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all flex-shrink-0"
          style={{ background: '#f97316' }}
        >
          + Upload File
        </button>
      </div>

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
          <div className="py-12 text-center text-xs" style={{ color: '#6B7280' }}>
            Loading files...
          </div>
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
                <th className="py-3">Folder</th>
                <th className="py-3">Size</th>
                <th className="py-3">Date</th>
                <th className="py-3 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((f) => (
                <tr
                  key={f.id}
                  className="border-t hover:bg-white/5 transition-colors"
                  style={{ borderColor: '#1E2A3A' }}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileTypeAvatar type={f.file_type} />
                      <span className="text-gray-200 truncate max-w-[260px]">{f.filename}</span>
                    </div>
                  </td>
                  <td className="py-3">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-mono font-medium"
                      style={{ background: '#1E2A3A', color: '#f97316' }}
                    >
                      {f.folderLabel}
                    </span>
                  </td>
                  <td className="py-3 text-xs font-mono" style={{ color: '#6B7280' }}>
                    {formatBytes(f.size_bytes)}
                  </td>
                  <td className="py-3 text-xs" style={{ color: '#6B7280' }}>
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
              File will be uploaded to the <span style={{ color: '#f97316' }}>{sectionTitle}</span> department folder.
            </p>
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
            {uploadError && (
              <p className="text-xs text-red-400 mb-3">{uploadError}</p>
            )}
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
