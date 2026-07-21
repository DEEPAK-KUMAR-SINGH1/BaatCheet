import { useEffect, useRef, useState } from 'react'
import { File, FileText, Image, Plus, Send, UploadCloud, X } from 'lucide-react'
import { uploadDoc, uploadWorkspaceDoc } from '../api/client.jsx'

const uploadTypes = [
  { label: 'PDF Document', accept: '.pdf', icon: FileText, color: 'text-red-500' },
  { label: 'Image OCR', accept: '.jpg,.jpeg,.png,.webp', icon: Image, color: 'text-blue-500' },
  { label: 'Text / CSV / Markdown', accept: '.txt,.md,.csv', icon: File, color: 'text-gray-500' },
  { label: 'Office Docs', accept: '.doc,.docx,.xlsx,.pptx', icon: FileText, color: 'text-emerald-500' },
]

function FileMenu({ onFilePick, onClose }) {
  const inputRef = useRef()
  const [accept, setAccept] = useState('')

  const pick = (acc) => {
    setAccept(acc)
    setTimeout(() => inputRef.current?.click(), 50)
  }

  return (
    <div className="absolute bottom-full left-0 mb-2 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 w-60 z-50">
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-3 pb-1">Upload to workspace</p>
      {uploadTypes.map(({ label, accept: acc, icon: Icon, color }) => (
        <button key={label} onClick={() => pick(acc)}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-primary-50 transition text-left">
          <Icon size={15} className={color} />
          <span className="text-sm text-gray-700">{label}</span>
        </button>
      ))}
      <input ref={inputRef} type="file" accept={accept} className="hidden"
        onChange={e => { if (e.target.files?.[0]) { onFilePick(e.target.files[0]); onClose() } }} />
    </div>
  )
}

export default function ChatInput({
  onSend,
  onFileUploaded,
  threadId,
  workspaceId,
  disabled,
  limitReached,
}) {
  const [text, setText] = useState('')
  const [showMenu, setShowMenu] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadName, setUploadName] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadErr, setUploadErr] = useState('')
  const [dragging, setDragging] = useState(false)
  const textareaRef = useRef()
  const menuRef = useRef()

  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [text])

  const handleSend = () => {
    const msg = text.trim()
    if (!msg || disabled) return
    onSend(msg)
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFile = async (file) => {
    if (!threadId) return
    setUploadErr('')
    setUploading(true)
    setUploadName(file.name)
    setUploadProgress(0)
    try {
      const res = workspaceId
        ? await uploadWorkspaceDoc(workspaceId, threadId, file, setUploadProgress)
        : await uploadDoc(threadId, file, setUploadProgress)
      onFileUploaded(res)
      if (res.status === 'failed') {
        setUploadErr(res.error || 'Upload saved, but indexing failed. Retry from the document panel.')
      }
    } catch (err) {
      setUploadErr(err.message || 'Upload failed')
      setTimeout(() => setUploadErr(''), 5000)
    } finally {
      setUploading(false)
      setUploadName('')
      setUploadProgress(0)
      setDragging(false)
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  if (limitReached) {
    return (
      <div className="px-4 py-3">
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-2xl px-4 py-3">
          <span className="text-sm text-red-500 flex-1">Chat limit reached. Contact admin for unlimited access.</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-3"
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}>
      {uploadErr && (
        <div className="mb-2 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 rounded-xl">
          <span className="flex-1">{uploadErr}</span>
          <button onClick={() => setUploadErr('')}><X size={13} /></button>
        </div>
      )}

      {uploading && (
        <div className="mb-2 bg-primary-50 border border-primary-200 rounded-xl px-3 py-2">
          <div className="flex items-center gap-2 text-xs text-primary-700 mb-1">
            <UploadCloud size={14} />
            <span className="font-medium truncate">{uploadName}</span>
            <span className="ml-auto">{uploadProgress || 5}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-primary-100 overflow-hidden">
            <div className="h-full bg-primary-500 transition-all" style={{ width: `${Math.max(uploadProgress, 5)}%` }} />
          </div>
        </div>
      )}

      {dragging && (
        <div className="mb-2 rounded-2xl border-2 border-dashed border-primary-300 bg-primary-50 px-4 py-4 text-center text-sm text-primary-700">
          Drop a PDF, image, text, CSV, Markdown, DOC, DOCX, XLSX, or PPTX file to index it.
        </div>
      )}

      <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl shadow-sm px-3 py-2.5
                      focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 transition">
        <div className="relative flex-shrink-0" ref={menuRef}>
          <button onClick={() => setShowMenu(v => !v)} disabled={uploading} title="Upload document"
            className={`w-8 h-8 rounded-xl flex items-center justify-center transition
              ${showMenu ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-500 hover:bg-primary-100 hover:text-primary-600'}
              ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            <Plus size={18} className={`transition-transform ${showMenu ? 'rotate-45' : ''}`} />
          </button>
          {showMenu && <FileMenu onFilePick={handleFile} onClose={() => setShowMenu(false)} />}
        </div>

        <textarea ref={textareaRef} rows={1} value={text}
          onChange={e => setText(e.target.value)} onKeyDown={handleKey}
          placeholder={disabled ? 'Please wait...' : 'Ask with documents, web, and calculator together...'}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400
                     focus:outline-none leading-relaxed max-h-40 py-1 disabled:opacity-50"
        />

        <button onClick={handleSend} disabled={!text.trim() || disabled}
          className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 transition
            ${text.trim() && !disabled
              ? 'bg-gradient-to-br from-primary-500 to-purple-600 text-white hover:opacity-90 shadow-sm'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}>
          <Send size={15} />
        </button>
      </div>

      <p className="text-center text-[10px] text-gray-400 mt-1.5">
        Drag files here or click +. Hybrid chat can use workspace docs, web search, and calculator together.
      </p>
    </div>
  )
}
