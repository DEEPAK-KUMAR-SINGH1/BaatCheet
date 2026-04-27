import { deleteDoc } from '../api/client.jsx'
import { FileText, Image, File, X, Loader2 } from 'lucide-react'

const iconMap = {
  '.pdf':  { icon: FileText, color: 'text-red-500',   bg: 'bg-red-50' },
  '.jpg':  { icon: Image,    color: 'text-blue-500',  bg: 'bg-blue-50' },
  '.jpeg': { icon: Image,    color: 'text-blue-500',  bg: 'bg-blue-50' },
  '.png':  { icon: Image,    color: 'text-blue-500',  bg: 'bg-blue-50' },
  '.webp': { icon: Image,    color: 'text-blue-500',  bg: 'bg-blue-50' },
  '.txt':  { icon: File,     color: 'text-gray-500',  bg: 'bg-gray-50' },
  '.md':   { icon: File,     color: 'text-gray-500',  bg: 'bg-gray-50' },
  '.csv':  { icon: File,     color: 'text-green-500', bg: 'bg-green-50' },
}

function DocChip({ doc, onDelete }) {
  const ext  = doc.file_type || '.txt'
  const cfg  = iconMap[ext] || iconMap['.txt']
  const Icon = cfg.icon

  return (
    <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-sm max-w-[220px] group">
      <div className={`w-7 h-7 rounded-lg ${cfg.bg} flex items-center justify-center flex-shrink-0`}>
        <Icon size={14} className={cfg.color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-700 truncate">{doc.filename}</p>
        <p className="text-[10px] text-gray-400">{doc.chunk_count} chunks</p>
      </div>
      <button onClick={() => onDelete(doc.doc_id)}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition flex-shrink-0">
        <X size={12} />
      </button>
    </div>
  )
}

export default function DocPanel({ docs, onDocsChange, uploadingFile }) {
  const handleDelete = async (doc_id) => {
    try {
      await deleteDoc(doc_id)
      onDocsChange(docs.filter(d => d.doc_id !== doc_id))
    } catch (err) { console.error('Delete failed:', err) }
  }

  if (docs.length === 0 && !uploadingFile) return null

  return (
    <div className="px-4 py-2 border-b border-gray-100 bg-primary-50/40">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold text-primary-600 bg-primary-100 px-2 py-1 rounded-lg flex-shrink-0">
          📄 Document Mode
        </span>
        {docs.map(doc => <DocChip key={doc.doc_id} doc={doc} onDelete={handleDelete} />)}
        {uploadingFile && (
          <div className="flex items-center gap-2 bg-white border border-primary-200 rounded-xl px-3 py-2 shadow-sm">
            <Loader2 size={14} className="text-primary-500 animate-spin" />
            <div>
              <p className="text-xs font-medium text-gray-700 truncate max-w-[140px]">{uploadingFile}</p>
              <p className="text-[10px] text-gray-400">Processing...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
