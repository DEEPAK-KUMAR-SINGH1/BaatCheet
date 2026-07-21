import { useState } from 'react'
import { deleteWorkspaceDoc, retryWorkspaceDoc } from '../api/client.jsx'
import { File, FileText, Image, Loader2, RefreshCw, X } from 'lucide-react'

const iconMap = {
  '.pdf': { icon: FileText, color: 'text-red-500', bg: 'bg-red-50' },
  '.jpg': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50' },
  '.jpeg': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50' },
  '.png': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50' },
  '.webp': { icon: Image, color: 'text-blue-500', bg: 'bg-blue-50' },
  '.txt': { icon: File, color: 'text-gray-500', bg: 'bg-gray-50' },
  '.md': { icon: File, color: 'text-gray-500', bg: 'bg-gray-50' },
  '.csv': { icon: File, color: 'text-green-500', bg: 'bg-green-50' },
  '.doc': { icon: FileText, color: 'text-emerald-500', bg: 'bg-emerald-50' },
  '.docx': { icon: FileText, color: 'text-emerald-500', bg: 'bg-emerald-50' },
  '.xlsx': { icon: FileText, color: 'text-emerald-500', bg: 'bg-emerald-50' },
  '.pptx': { icon: FileText, color: 'text-orange-500', bg: 'bg-orange-50' },
}

function Status({ doc }) {
  if (doc.status === 'failed') {
    return <span className="text-[10px] font-semibold text-red-500">Failed</span>
  }
  if (doc.status === 'processing') {
    return <span className="text-[10px] font-semibold text-primary-500">Processing</span>
  }
  return <span className="text-[10px] text-gray-400">{doc.chunk_count} chunks</span>
}

function DocChip({ doc, onDelete, onRetry, onPreview, busy }) {
  const ext = doc.file_type || '.txt'
  const cfg = iconMap[ext] || iconMap['.txt']
  const Icon = cfg.icon

  return (
    <div className={`flex items-center gap-2 bg-white border rounded-xl px-3 py-2 shadow-sm max-w-[260px] group
      ${doc.status === 'failed' ? 'border-red-200' : 'border-gray-200'}`}>
      <button onClick={() => onPreview(doc)}
        className={`w-7 h-7 rounded-lg ${cfg.bg} flex items-center justify-center flex-shrink-0`}>
        <Icon size={14} className={cfg.color} />
      </button>
      <button onClick={() => onPreview(doc)} className="flex-1 min-w-0 text-left">
        <p className="text-xs font-medium text-gray-700 truncate">{doc.filename}</p>
        <Status doc={doc} />
      </button>
      {doc.status === 'failed' && (
        <button onClick={() => onRetry(doc)} disabled={busy}
          className="p-1 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition flex-shrink-0">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
        </button>
      )}
      <button onClick={() => onDelete(doc.doc_id)}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition flex-shrink-0">
        <X size={12} />
      </button>
    </div>
  )
}

export default function DocPanel({
  docs,
  onDocsChange,
  workspace,
  workspaces,
  onWorkspaceChange,
  onCreateWorkspace,
  selectedDoc,
  onPreviewDoc,
}) {
  const [retrying, setRetrying] = useState('')

  const handleDelete = async (doc_id) => {
    if (!workspace?.workspace_id) return
    try {
      await deleteWorkspaceDoc(workspace.workspace_id, doc_id)
      onDocsChange(docs.filter(d => d.doc_id !== doc_id))
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  const handleRetry = async (doc) => {
    if (!workspace?.workspace_id) return
    setRetrying(doc.doc_id)
    try {
      const updated = await retryWorkspaceDoc(workspace.workspace_id, doc.doc_id)
      onDocsChange(docs.map(d => d.doc_id === doc.doc_id ? updated : d))
    } catch (err) {
      onDocsChange(docs.map(d => d.doc_id === doc.doc_id ? { ...d, status: 'failed', error: err.message } : d))
    } finally {
      setRetrying('')
    }
  }

  return (
    <div className="px-4 py-2 border-b border-gray-100 bg-primary-50/40">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold text-primary-600 bg-primary-100 px-2 py-1 rounded-lg flex-shrink-0">
          Workspace
        </span>

        <select value={workspace?.workspace_id || ''}
          onChange={e => onWorkspaceChange(e.target.value || null)}
          className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-1.5 text-gray-700 focus:outline-none focus:border-primary-300">
          <option value="">No workspace</option>
          {workspaces.map(w => (
            <option key={w.workspace_id} value={w.workspace_id}>
              {w.name} ({w.document_count || 0})
            </option>
          ))}
        </select>

        <button onClick={onCreateWorkspace}
          className="text-xs font-semibold px-2 py-1.5 rounded-lg border border-primary-200 bg-white text-primary-600 hover:bg-primary-50">
          New
        </button>

        {docs.map(doc => (
          <DocChip key={doc.doc_id} doc={doc} onDelete={handleDelete} onRetry={handleRetry}
            onPreview={onPreviewDoc} busy={retrying === doc.doc_id} />
        ))}

        {docs.length === 0 && (
          <span className="text-xs text-gray-400">Upload documents once, reuse them across chats.</span>
        )}
      </div>

      {selectedDoc && (
        <div className="mt-2 bg-white border border-gray-100 rounded-2xl px-3 py-2 text-xs text-gray-600">
          <div className="flex items-center gap-2 mb-1">
            <strong className="text-gray-800 truncate">{selectedDoc.filename}</strong>
            <span className="text-gray-400">{selectedDoc.file_type}</span>
            <button onClick={() => onPreviewDoc(null)} className="ml-auto text-gray-400 hover:text-gray-600">
              <X size={13} />
            </button>
          </div>
          {selectedDoc.status === 'failed' ? (
            <p className="text-red-600">{selectedDoc.error || 'Indexing failed.'}</p>
          ) : (
            <p className="line-clamp-3 whitespace-pre-wrap">
              {selectedDoc.extracted_preview || 'Preview will appear after indexing.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
