import { useState } from 'react'
import { renameThread, deleteThread } from '../api/client.jsx'
import { useAuth } from '../hooks/useAuth.jsx'
import { Plus, MessageSquare, Pencil, Trash2, Check, X, LogOut, Bot, ExternalLink, Shield } from 'lucide-react'

export default function Sidebar({ threads, activeId, onSelect, onNew, onDeleted, onRenamed, onAdminClick }) {
  const { email, isAdmin, isApproved, chatCount, logout } = useAuth()
  const [renameId, setRenameId]   = useState(null)
  const [renameVal, setRenameVal] = useState('')

  const startRename = (t) => { setRenameId(t.thread_id); setRenameVal(t.title) }

  const submitRename = async (tid) => {
    if (!renameVal.trim()) return
    try { await renameThread(tid, renameVal.trim()); onRenamed(tid, renameVal.trim()) } catch {}
    setRenameId(null)
  }

  const handleDelete = async (tid) => {
    try { await deleteThread(tid); onDeleted(tid) } catch {}
  }

  // Role badge
  const roleBadge = isAdmin
    ? <span className="ml-1.5 text-[10px] font-bold bg-red-100 text-red-600 px-1.5 py-0.5 rounded-md">ADMIN</span>
    : isApproved
    ? <span className="ml-1.5 text-[10px] font-bold bg-green-100 text-green-600 px-1.5 py-0.5 rounded-md">PRO</span>
    : <span className="ml-1.5 text-[10px] font-bold bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-md">FREE</span>

  return (
    <aside className="w-64 flex-shrink-0 bg-white border-r border-gray-100 flex flex-col h-full">

      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center">
            <Bot size={18} className="text-white" />
          </div>
          <span className="font-bold text-gray-800">AI Assistant</span>
        </div>
        <p className="text-xs text-gray-400 mt-1 ml-10">Mistral · LangGraph</p>
      </div>

      {/* Admin Dashboard button — sirf admin ke liye */}
      {isAdmin && (
        <div className="px-3 pt-3">
          <button onClick={onAdminClick}
            className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl
                       bg-red-50 border border-red-200 text-red-600
                       text-sm font-semibold hover:bg-red-100 transition">
            <Shield size={15} /> Admin Dashboard
          </button>
        </div>
      )}

      {/* New Chat */}
      <div className="px-3 py-3">
        <button onClick={onNew}
          className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl
                     bg-gradient-to-r from-primary-500 to-purple-600
                     text-white text-sm font-semibold hover:opacity-90 transition">
          <Plus size={16} /> New Chat
        </button>
      </div>

      {/* Free user chat limit bar */}
      {!isAdmin && !isApproved && (
        <div className="px-3 pb-2">
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-3 py-2.5">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-semibold text-yellow-800">Free plan</span>
              <span className="text-xs font-bold text-yellow-800">{Math.min(chatCount, 5)}/5</span>
            </div>
            <div className="w-full bg-yellow-200 rounded-full h-1.5">
              <div
                className="bg-yellow-500 h-1.5 rounded-full transition-all"
                style={{ width: `${Math.min((chatCount / 5) * 100, 100)}%` }}
              />
            </div>
            <p className="text-[10px] text-yellow-700 mt-1.5">
              {chatCount >= 5
                ? '⛔ Limit reached — contact admin'
                : `${5 - chatCount} chats remaining`}
            </p>
          </div>
        </div>
      )}

      {/* Threads */}
      <div className="flex-1 overflow-y-auto px-3 py-1">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mb-2">Conversations</p>

        {threads.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">No conversations yet</p>
        )}

        {threads.map(t => (
          <div key={t.thread_id}
            className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl mb-1 cursor-pointer transition
              ${activeId === t.thread_id ? 'bg-primary-50 border border-primary-100' : 'hover:bg-gray-50'}`}
            onClick={() => renameId !== t.thread_id && onSelect(t.thread_id)}>

            <MessageSquare size={14}
              className={activeId === t.thread_id ? 'text-primary-500 flex-shrink-0' : 'text-gray-400 flex-shrink-0'} />

            {renameId === t.thread_id ? (
              <input autoFocus value={renameVal}
                onChange={e => setRenameVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submitRename(t.thread_id); if (e.key === 'Escape') setRenameId(null) }}
                onClick={e => e.stopPropagation()}
                className="flex-1 text-sm bg-white border border-primary-300 rounded-lg px-2 py-0.5 focus:outline-none min-w-0"
              />
            ) : (
              <span className={`flex-1 text-sm truncate ${activeId === t.thread_id ? 'text-primary-700 font-medium' : 'text-gray-700'}`}>
                {t.title}
              </span>
            )}

            {renameId === t.thread_id ? (
              <div className="flex gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                <button onClick={() => submitRename(t.thread_id)} className="p-1 text-green-500 hover:bg-green-50 rounded-lg"><Check size={13} /></button>
                <button onClick={() => setRenameId(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded-lg"><X size={13} /></button>
              </div>
            ) : (
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 flex-shrink-0 transition" onClick={e => e.stopPropagation()}>
                <button onClick={() => startRename(t)} className="p-1 text-gray-400 hover:text-primary-500 hover:bg-primary-50 rounded-lg"><Pencil size={12} /></button>
                <button onClick={() => handleDelete(t.thread_id)} className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg"><Trash2 size={12} /></button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-100 px-3 py-3 space-y-1">
        <a href="https://smith.langchain.com" target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition">
          <ExternalLink size={13} /> LangSmith Traces
        </a>
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl">
          <div className="w-6 h-6 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-primary-600">{email?.[0]?.toUpperCase() || '?'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center">
              <span className="text-xs text-gray-600 truncate">{email}</span>
              {roleBadge}
            </div>
          </div>
          <button onClick={logout} className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition">
            <LogOut size={13} />
          </button>
        </div>
      </div>
    </aside>
  )
}
