import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { renameThread, deleteThread } from '../api/client.jsx'
import { useAuth } from '../hooks/useAuth.jsx'
import {
  BarChart3,
  Bot,
  Check,
  ChevronRight,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  UserCircle,
  X,
} from 'lucide-react'

function AccountAvatar({ email, size = 'md' }) {
  const classes = size === 'sm' ? 'w-7 h-7 text-[10px]' : 'w-9 h-9 text-xs'
  return (
    <div className={`${classes} rounded-full bg-amber-500 text-white flex items-center justify-center flex-shrink-0`}>
      <span className="font-bold">{(email?.[0] || '?').toUpperCase()}</span>
    </div>
  )
}

function AccountPortal({
  open,
  anchorRef,
  email,
  displayName,
  planLabel,
  isAdmin,
  onClose,
  onAdminClick,
  onLogout,
}) {
  const portalRef = useRef(null)
  const [position, setPosition] = useState({ left: 272, top: 120 })

  useEffect(() => {
    if (!open) return

    const updatePosition = () => {
      const rect = anchorRef.current?.getBoundingClientRect()
      if (!rect) return
      const width = 420
      const gap = 10
      const left = Math.min(rect.right + gap, Math.max(12, window.innerWidth - width - 12))
      const top = Math.min(Math.max(12, rect.top - 280), window.innerHeight - 520)
      setPosition({ left, top: Math.max(12, top) })
    }

    const onPointerDown = (event) => {
      if (portalRef.current?.contains(event.target) || anchorRef.current?.contains(event.target)) return
      onClose()
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [anchorRef, onClose, open])

  if (!open) return null

  const adminItems = [
    { icon: LayoutDashboard, label: 'Admin Panel', section: 'dashboard' },
    { icon: UserCircle, label: 'Admin profile', section: 'profile' },
    { icon: BarChart3, label: 'Analytics', section: 'analytics' },
    { icon: MessageSquare, label: 'Chat history', section: 'chat-history' },
    { icon: SlidersHorizontal, label: 'Settings and controls', section: 'settings' },
  ]
  const openAdminSection = (section) => {
    if (isAdmin) onAdminClick?.(section)
  }
  const userItems = [
    { icon: Sparkles, label: 'Personalization', action: () => openAdminSection('settings') },
    { icon: UserCircle, label: 'Profile', action: () => openAdminSection('profile') },
    { icon: HelpCircle, label: 'Help', action: () => window.open('https://smith.langchain.com', '_blank', 'noopener,noreferrer'), trailing: true },
  ]

  const run = (action) => {
    onClose()
    action?.()
  }

  return createPortal(
    <div
      ref={portalRef}
      className="fixed z-50 max-h-[calc(100vh-24px)] w-[min(420px,calc(100vw-24px))] overflow-y-auto rounded-2xl border border-gray-200 bg-white shadow-2xl account-portal"
      style={{ left: position.left, top: position.top }}
    >
      <div className="px-5 pt-4 pb-3">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <UserCircle size={18} />
          <span className="truncate">{email}</span>
        </div>
      </div>

      <div className="mx-4 mb-2 rounded-xl bg-gray-50 px-3 py-3 flex items-center gap-3">
        <AccountAvatar email={email} size="sm" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate capitalize">{displayName}</p>
          <p className="text-xs text-gray-400">{planLabel}</p>
        </div>
        <Check size={18} className="text-gray-800" />
      </div>

      <div className="px-4 pb-2">
        <button onClick={() => run(onLogout)}
          className="w-full flex items-center gap-3 px-2 py-2.5 rounded-xl text-sm text-gray-700 hover:bg-gray-50">
          <Plus size={18} className="text-gray-500" />
          <span className="flex-1 text-left">Add account</span>
        </button>
      </div>

      {isAdmin && (
        <div className="px-4 py-2 border-t border-gray-100">
          <p className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-wide text-gray-400">Admin Panel</p>
          {adminItems.map(item => (
            <button key={item.section}
              onClick={() => run(() => onAdminClick?.(item.section))}
              className="w-full flex items-center gap-3 px-2 py-2.5 rounded-xl text-sm text-gray-700 hover:bg-gray-50">
              <item.icon size={18} className="text-gray-500" />
              <span className="flex-1 text-left">{item.label}</span>
              <ChevronRight size={16} className="text-gray-300" />
            </button>
          ))}
        </div>
      )}

      <div className="px-4 py-2 border-t border-gray-100">
        {userItems.map(item => (
          <button key={item.label}
            onClick={() => run(item.action)}
            className="w-full flex items-center gap-3 px-2 py-2.5 rounded-xl text-sm text-gray-700 hover:bg-gray-50">
            <item.icon size={18} className="text-gray-500" />
            <span className="flex-1 text-left">{item.label}</span>
            {item.trailing && <ChevronRight size={16} className="text-gray-300" />}
          </button>
        ))}
      </div>

      <div className="px-4 py-3 border-t border-gray-100">
        <button onClick={() => run(onLogout)}
          className="w-full flex items-center gap-3 px-2 py-2.5 rounded-xl text-sm text-gray-700 hover:bg-red-50 hover:text-red-600">
          <LogOut size={18} />
          <span className="flex-1 text-left">Log out</span>
        </button>
      </div>
    </div>,
    document.body,
  )
}

export default function Sidebar({
  threads,
  activeId,
  onSelect,
  onNew,
  onDeleted,
  onRenamed,
  onAdminClick,
  searchQuery,
  onSearchChange,
  searchResults,
}) {
  const { email, isAdmin, isApproved, chatCount, logout } = useAuth()
  const [renameId, setRenameId]   = useState(null)
  const [renameVal, setRenameVal] = useState('')
  const [accountOpen, setAccountOpen] = useState(false)
  const accountButtonRef = useRef(null)

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
  const displayName = email?.split('@')[0]?.replace(/[._-]+/g, ' ') || 'User'
  const planLabel = isAdmin ? 'Admin' : isApproved ? 'Pro' : 'Free'

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

      <div className="px-3 pb-2">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={searchQuery}
            onChange={e => onSearchChange?.(e.target.value)}
            placeholder="Search chats..."
            className="w-full pl-8 pr-3 py-2 rounded-xl border border-gray-200 text-xs focus:outline-none focus:border-primary-300" />
        </div>
        {searchQuery && searchResults?.length > 0 && (
          <div className="mt-2 max-h-44 overflow-y-auto bg-white border border-gray-100 rounded-xl shadow-sm">
            {searchResults.slice(0, 6).map((result, idx) => (
              <button key={`${result.thread_id}-${idx}`} onClick={() => onSelect(result.thread_id)}
                className="w-full text-left px-3 py-2 hover:bg-primary-50 border-b border-gray-50 last:border-0">
                <p className="text-xs font-semibold text-gray-700 truncate">{result.title}</p>
                <p className="text-[10px] text-gray-400 truncate">{result.match_type}: {result.snippet}</p>
              </button>
            ))}
          </div>
        )}
      </div>

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

      <div className="border-t border-gray-100 px-2.5 py-2.5">
        <button ref={accountButtonRef}
          onClick={() => setAccountOpen(open => !open)}
          className={`w-full flex items-center gap-3 px-2.5 py-2.5 rounded-xl text-left transition
            ${accountOpen ? 'bg-gray-100' : 'hover:bg-gray-50'}`}>
          <AccountAvatar email={email} size="sm" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center min-w-0">
              <span className="text-sm font-semibold text-gray-800 truncate capitalize">{displayName}</span>
              {roleBadge}
            </div>
            <p className="text-xs text-gray-400 truncate">{planLabel}</p>
          </div>
          <ChevronRight size={18} className={`text-gray-400 transition ${accountOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      <AccountPortal
        open={accountOpen}
        anchorRef={accountButtonRef}
        email={email}
        displayName={displayName}
        planLabel={planLabel}
        isAdmin={isAdmin}
        onClose={() => setAccountOpen(false)}
        onAdminClick={onAdminClick}
        onLogout={logout}
      />
    </aside>
  )
}
