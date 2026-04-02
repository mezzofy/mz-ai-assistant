import React, { useState, useEffect } from 'react'
import { Download } from 'lucide-react'
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
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

interface Props {
  department: string
  sectionTitle: string
}

export default function DeptFilesPage({ department, sectionTitle }: Props) {
  const [companyFiles, setCompanyFiles] = useState<FileRecord[]>([])
  const [deptFiles, setDeptFiles] = useState<FileRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
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
        setCompanyFiles(extractFiles(companyRes))
        setDeptFiles(extractFiles(deptRes))
      })
      .catch(() => setError('Failed to load files. Please try again.'))
      .finally(() => setLoading(false))
  }, [department])

  const handleDownload = (file: FileRecord) => {
    portalApi.downloadDeptFile(file.id, file.filename)
  }

  const FileTable = ({ files, emptyText }: { files: FileRecord[]; emptyText: string }) => {
    if (loading) {
      return <p className="text-sm px-4 py-3" style={{ color: '#6B7280' }}>Loading files...</p>
    }
    if (error) {
      return <p className="text-sm px-4 py-3 text-red-400">{error}</p>
    }
    if (files.length === 0) {
      return <p className="text-sm px-4 py-3" style={{ color: '#6B7280' }}>{emptyText}</p>
    }
    return (
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: '1px solid #1E2A3A' }}>
            <th className="text-left px-4 py-2 font-medium" style={{ color: '#6B7280' }}>Name</th>
            <th className="text-left py-2 font-medium" style={{ color: '#6B7280' }}>Size</th>
            <th className="text-left py-2 font-medium" style={{ color: '#6B7280' }}>Date</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {files.map((file) => (
            <tr key={file.id} style={{ borderBottom: '1px solid #1E2A3A' }}>
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <FileTypeAvatar type={file.file_type} />
                  <span className="text-white">{file.filename}</span>
                </div>
              </td>
              <td className="py-2" style={{ color: '#6B7280' }}>{formatBytes(file.size_bytes)}</td>
              <td className="py-2" style={{ color: '#6B7280' }}>
                {file.created_at ? new Date(file.created_at).toLocaleDateString() : '—'}
              </td>
              <td className="py-2 pr-4 text-right">
                <button
                  onClick={() => handleDownload(file)}
                  className="flex items-center gap-1 px-3 py-1 rounded text-xs transition-all"
                  style={{ background: '#1E2A3A', color: '#f97316' }}
                >
                  <Download size={12} /> Download
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  return (
    <div className="p-6 space-y-6" style={{ background: '#0A0E1A', minHeight: '100vh' }}>
      <div>
        <h1 className="text-xl font-bold text-white">Files</h1>
        <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
          Company and {sectionTitle} department files
        </p>
      </div>

      <div className="rounded-lg overflow-hidden" style={{ background: '#111827', border: '1px solid #1E2A3A' }}>
        <div className="px-4 py-3" style={{ borderBottom: '1px solid #1E2A3A' }}>
          <h2 className="text-sm font-semibold text-white">🏢 Company Files</h2>
        </div>
        <FileTable files={companyFiles} emptyText="No company files found." />
      </div>

      <div className="rounded-lg overflow-hidden" style={{ background: '#111827', border: '1px solid #1E2A3A' }}>
        <div className="px-4 py-3" style={{ borderBottom: '1px solid #1E2A3A' }}>
          <h2 className="text-sm font-semibold text-white">📁 {sectionTitle} Files</h2>
        </div>
        <FileTable files={deptFiles} emptyText={`No ${sectionTitle} department files found.`} />
      </div>
    </div>
  )
}
