import { useState, useRef, useEffect } from 'react'
import { Send, Plus, X, FileText, Image, File } from 'lucide-react'
import { uploadDoc } from '../api/client.jsx'

function FileMenu({ onFilePick, onClose }) {
  const types = [
    { label: 'PDF Document',    accept: '.pdf',               icon: <FileText size={15} className="text-red-500" /> },
    { label: 'Image (JPG/PNG)', accept: '.jpg,.jpeg,.png,.webp', icon: <Image size={15} className="text-blue-500" /> },
    { label: 'Text / CSV / MD', accept: '.txt,.md,.csv',     icon: <File size={15} className="text-gray-500" /> },
  ]
  const inputRef = useRef()
  const [accept, setAccept] = useState('')

  const pick = (acc) => { setAccept(acc); setTimeout(() => inputRef.current?.click(), 50) }

  return (
    <div className="absolute bottom-full left-0 mb-2 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 w-52 z-50">
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-3 pb-1">Upload Document</p>
      {types.map(t => (
        <button key={t.label} onClick={() => pick(t.accept)}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-primary-50 transition text-left">
          {t.icon}
          <span className="text-sm text-gray-700">{t.label}</span>
        </button>
      ))}
      <input ref={inputRef} type="file" accept={accept} className="hidden"
        onChange={e => { if (e.target.files?.[0]) { onFilePick(e.target.files[0]); onClose() } }} />
    </div>
  )
}

export default function ChatInput({ onSend, onFileUploaded, threadId, disabled, limitReached }) {
  const [text, setText]           = useState('')
  const [showMenu, setShowMenu]   = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState('')
  const textareaRef = useRef()
  const menuRef     = useRef()

  useEffect(() => {
    const handler = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false) }
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
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleFile = async (file) => {
    setUploadErr('')
    setUploading(true)
    try {
      const res = await uploadDoc(threadId, file)
      onFileUploaded(res)
    } catch (err) {
      setUploadErr(err.message || 'Upload failed')
      setTimeout(() => setUploadErr(''), 4000)
    } finally { setUploading(false) }
  }

  // Limit reach hone pe disabled input dikhao
  if (limitReached) {
    return (
      <div className="px-4 py-3">
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-2xl px-4 py-3">
          <span className="text-sm text-red-500 flex-1">⛔ Chat limit reached — contact admin for unlimited access</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-3">
      {uploadErr && (
        <div className="mb-2 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 rounded-xl">
          <span className="flex-1">{uploadErr}</span>
          <button onClick={() => setUploadErr('')}><X size={13} /></button>
        </div>
      )}

      <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl shadow-sm px-3 py-2.5
                      focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 transition">

        {/* + Upload Button */}
        <div className="relative flex-shrink-0" ref={menuRef}>
          <button onClick={() => setShowMenu(v => !v)} disabled={uploading} title="Upload document"
            className={`w-8 h-8 rounded-xl flex items-center justify-center transition
              ${showMenu ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-500 hover:bg-primary-100 hover:text-primary-600'}
              ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {uploading
              ? <div className="w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
              : <Plus size={18} className={`transition-transform ${showMenu ? 'rotate-45' : ''}`} />
            }
          </button>
          {showMenu && <FileMenu onFilePick={handleFile} onClose={() => setShowMenu(false)} />}
        </div>

        {/* Textarea */}
        <textarea ref={textareaRef} rows={1} value={text}
          onChange={e => setText(e.target.value)} onKeyDown={handleKey}
          placeholder={disabled ? 'Please wait...' : 'Ask me anything... (Shift+Enter for new line)'}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400
                     focus:outline-none leading-relaxed max-h-40 py-1 disabled:opacity-50"
        />

        {/* Send Button */}
        <button onClick={handleSend} disabled={!text.trim() || disabled}
          className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 transition
            ${text.trim() && !disabled
              ? 'bg-gradient-to-br from-primary-500 to-purple-600 text-white hover:opacity-90 shadow-sm'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}>
          <Send size={15} />
        </button>
      </div>

      <p className="text-center text-[10px] text-gray-400 mt-1.5">
        Click <strong>+</strong> to upload PDF or image for Document Q&A mode.
      </p>
    </div>
  )
}
