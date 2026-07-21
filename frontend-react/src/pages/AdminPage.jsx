import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import {
  adminApproveUser,
  adminDeleteDocument,
  adminDeleteThread,
  adminGetAnalytics,
  adminGetDocuments,
  adminGetThreads,
  adminGetUsers,
  adminRevokeUser,
} from '../api/client.jsx'
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Bot,
  Check,
  CheckCircle,
  Database,
  FileText,
  FolderOpen,
  Gauge,
  History,
  Mail,
  RefreshCw,
  Search,
  Settings,
  Shield,
  SlidersHorizontal,
  Trash2,
  UserCircle,
  Users,
  X,
} from 'lucide-react'

function StatCard({ label, value, color = 'gray', icon: Icon }) {
  const colors = {
    gray: 'bg-white border-gray-100 text-gray-700',
    green: 'bg-green-50 border-green-100 text-green-700',
    yellow: 'bg-yellow-50 border-yellow-100 text-yellow-700',
    red: 'bg-red-50 border-red-100 text-red-600',
    blue: 'bg-blue-50 border-blue-100 text-blue-700',
  }
  return (
    <div className={`border rounded-xl px-4 py-4 flex items-center gap-3 ${colors[color]}`}>
      {Icon && (
        <div className="w-9 h-9 rounded-lg bg-white/70 border border-current/10 flex items-center justify-center">
          <Icon size={16} />
        </div>
      )}
      <div className="min-w-0">
        <span className="block text-2xl font-bold leading-none">{value}</span>
        <span className="block text-xs font-medium opacity-70 mt-1 truncate">{label}</span>
      </div>
    </div>
  )
}

function Badge({ approved, isAdmin, verified = true }) {
  if (isAdmin) {
    return <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-red-600">Admin</span>
  }
  if (!verified) {
    return <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-gray-100 text-gray-600">Unverified</span>
  }
  if (approved) {
    return <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-green-700">Approved</span>
  }
  return <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-yellow-100 text-yellow-700">Pending</span>
}

function SectionTitle({ id, icon: Icon, title, description }) {
  return (
    <div id={id} className="scroll-mt-6 flex items-center gap-3 mb-3">
      <div className="w-9 h-9 rounded-xl bg-white border border-gray-100 flex items-center justify-center">
        <Icon size={16} className="text-primary-500" />
      </div>
      <div>
        <h2 className="text-sm font-bold text-gray-800">{title}</h2>
        <p className="text-xs text-gray-400">{description}</p>
      </div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3 text-xs py-2 border-b border-gray-50 last:border-0">
      <span className="text-gray-400">{label}</span>
      <span className="font-semibold text-gray-700 text-right truncate">{value || 'Not available'}</span>
    </div>
  )
}

function ManagementTile({ icon: Icon, title, description, meta, onClick }) {
  return (
    <button onClick={onClick}
      className="text-left bg-white border border-gray-100 rounded-xl p-4 hover:border-primary-200 hover:bg-primary-50/40 transition">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center flex-shrink-0">
          <Icon size={16} />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold text-gray-800">{title}</p>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed">{description}</p>
          {meta && <p className="text-[11px] font-semibold text-primary-600 mt-2">{meta}</p>}
        </div>
      </div>
    </button>
  )
}

function StatusPill({ label, value = 'Enabled', color = 'green' }) {
  const colors = {
    green: 'bg-green-50 text-green-700 border-green-100',
    gray: 'bg-gray-50 text-gray-600 border-gray-100',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-100',
  }
  return (
    <span className={`inline-flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 text-[11px] font-semibold ${colors[color]}`}>
      <span>{label}</span>
      <span>{value}</span>
    </span>
  )
}

function shortDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const adminSections = [
  ['profile', 'Profile'],
  ['dashboard', 'Dashboard'],
  ['analytics', 'Analytics'],
  ['users', 'Users'],
  ['chat-history', 'Chats'],
  ['library', 'Library'],
  ['settings', 'Settings'],
  ['mcp', 'MCP Integrations'],
]

export default function AdminPage() {
  const { email, isAdmin, isApproved, chatCount } = useAuth()
  const navigate = useNavigate()

  const [users, setUsers] = useState([])
  const [threads, setThreads] = useState([])
  const [documents, setDocuments] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [actionEmail, setActionEmail] = useState('')
  const [actionThread, setActionThread] = useState('')
  const [actionDoc, setActionDoc] = useState('')

  useEffect(() => {
    if (!isAdmin) {
      navigate('/')
      return
    }
    loadAdminData()
  }, [isAdmin])

  useEffect(() => {
    if (loading) return
    const hash = window.location.hash.replace('#', '')
    if (!hash) return
    requestAnimationFrame(() => scrollToSection(hash))
  }, [loading])

  const loadAdminData = async () => {
    setLoading(true)
    setError('')
    try {
      const [userData, analyticsData, threadData, documentData] = await Promise.all([
        adminGetUsers(),
        adminGetAnalytics(30),
        adminGetThreads(50),
        adminGetDocuments(50),
      ])
      setUsers(userData)
      setAnalytics(analyticsData)
      setThreads(threadData)
      setDocuments(documentData)
    } catch (e) {
      setError('Failed to load admin panel: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (targetEmail) => {
    setActionEmail(targetEmail)
    try {
      await adminApproveUser(targetEmail)
      setUsers(prev => prev.map(u => u.email === targetEmail ? { ...u, is_approved: 1 } : u))
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setActionEmail('')
    }
  }

  const handleRevoke = async (targetEmail) => {
    setActionEmail(targetEmail)
    try {
      await adminRevokeUser(targetEmail)
      setUsers(prev => prev.map(u => u.email === targetEmail ? { ...u, is_approved: 0 } : u))
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setActionEmail('')
    }
  }

  const handleDeleteThread = async (thread) => {
    if (!window.confirm(`Delete chat "${thread.title}"? This removes its messages.`)) return
    setActionThread(thread.thread_id)
    try {
      await adminDeleteThread(thread.thread_id)
      setThreads(prev => prev.filter(item => item.thread_id !== thread.thread_id))
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setActionThread('')
    }
  }

  const handleDeleteDocument = async (doc) => {
    if (!window.confirm(`Delete document "${doc.filename}" from the library?`)) return
    setActionDoc(doc.doc_id)
    try {
      await adminDeleteDocument(doc.doc_id)
      setDocuments(prev => prev.filter(item => item.doc_id !== doc.doc_id))
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setActionDoc('')
    }
  }

  const displayName = useMemo(
    () => email?.split('@')[0]?.replace(/[._-]+/g, ' ') || 'Admin User',
    [email],
  )
  const currentUser = users.find(u => u.email === email)
  const nonAdmins = users.filter(u => !u.is_admin)
  const approved = nonAdmins.filter(u => u.is_approved).length
  const pending = nonAdmins.filter(u => !u.is_approved).length
  const totals = analytics?.totals || {}
  const queueAge = analytics?.approval_queue?.[0]?.age_hours || 0

  const filteredUsers = users.filter(u => {
    if (u.is_admin) return false
    if (filter === 'approved' && !u.is_approved) return false
    if (filter === 'pending' && u.is_approved) return false
    if (search && !u.email.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4 sticky top-0 z-10">
        <button onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition">
          <ArrowLeft size={16} /> Back to Chat
        </button>
        <div className="flex-1 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-red-100 flex items-center justify-center">
            <Shield size={16} className="text-red-500" />
          </div>
          <div>
            <h1 className="font-bold text-gray-800 text-sm leading-tight">Admin Panel</h1>
            <p className="text-xs text-gray-400">Users, chatbot activity, library, and settings</p>
          </div>
        </div>
        <button onClick={loadAdminData} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-50 transition">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">{error}</div>
        )}

        <div className="bg-white border border-gray-100 rounded-xl px-2 py-2 flex gap-1 overflow-x-auto">
          {adminSections.map(([id, label]) => (
            <button key={id}
              onClick={() => {
                window.history.replaceState({}, '', `#${id}`)
                scrollToSection(id)
              }}
              className="px-3 py-2 rounded-lg text-xs font-semibold text-gray-500 hover:bg-gray-50 hover:text-gray-800 whitespace-nowrap">
              {label}
            </button>
          ))}
        </div>

        <section>
          <SectionTitle id="profile" icon={UserCircle} title="User Profile" description="Current admin identity and account details" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-primary-100 flex items-center justify-center">
                  <span className="text-lg font-bold text-primary-600">{email?.[0]?.toUpperCase() || 'A'}</span>
                </div>
                <div className="min-w-0">
                  <p className="text-base font-bold text-gray-800 capitalize truncate">{displayName}</p>
                  <p className="text-xs text-gray-400 truncate">{email}</p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge approved={isApproved} isAdmin={isAdmin} />
                <StatusPill label="Profile" value="Active" />
              </div>
            </div>

            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Profile Information</h3>
              <InfoRow label="User Name" value={displayName} />
              <InfoRow label="Email Address" value={email} />
              <InfoRow label="Role" value={isAdmin ? 'Administrator' : 'User'} />
            </div>

            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Account Details</h3>
              <InfoRow label="Access Plan" value={isApproved || isAdmin ? 'Unlimited' : 'Free'} />
              <InfoRow label="Chats Used" value={String(chatCount ?? currentUser?.chat_count ?? 0)} />
              <InfoRow label="Joined" value={shortDate(currentUser?.created_at)} />
            </div>
          </div>
        </section>

        <section>
          <SectionTitle id="dashboard" icon={LayoutDashboardIcon} title="Admin Dashboard" description="Management entry points for the chatbot system" />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <ManagementTile icon={Users} title="Users and Access" description="Review users, approve unlimited access, and revoke access." meta={`${approved} approved, ${pending} pending`} onClick={() => scrollToSection('users')} />
            <ManagementTile icon={Activity} title="Activity and Analytics" description="Track chats, daily active users, documents, and failure reasons." meta={`${totals.chats || 0} total chats`} onClick={() => scrollToSection('analytics')} />
            <ManagementTile icon={History} title="Chat History" description="Inspect recent chatbot conversations and remove stale threads." meta={`${threads.length} recent threads loaded`} onClick={() => scrollToSection('chat-history')} />
            <ManagementTile icon={FolderOpen} title="File Library" description="Manage uploaded documents, indexing state, and failed files." meta={`${documents.length} documents loaded`} onClick={() => scrollToSection('library')} />
            <ManagementTile icon={SlidersHorizontal} title="Chatbot Settings" description="See current tool, app, sharing, and retrieval controls." meta="Feature controls" onClick={() => scrollToSection('settings')} />
            <ManagementTile icon={Mail} title="Connected Apps" description="Monitor Gmail MCP readiness from the chatbot header connection flow." meta="Gmail MCP available" onClick={() => navigate('/')} />
          </div>
        </section>

        <section>
          <SectionTitle id="analytics" icon={BarChart3} title="User Statistics and Analytics" description="Operational totals and recent activity" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <StatCard label="Total users" value={nonAdmins.length} icon={Users} />
            <StatCard label="Approved users" value={approved} color="green" icon={CheckCircle} />
            <StatCard label="Pending users" value={pending} color="yellow" icon={Gauge} />
            <StatCard label="Total chats" value={totals.chats || 0} color="blue" icon={Bot} />
            <StatCard label="Documents" value={totals.documents || 0} color="green" icon={FileText} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">Daily active users</h3>
              <div className="space-y-2 max-h-44 overflow-y-auto">
                {(analytics?.daily_active_users || []).slice(0, 8).map(row => (
                  <div key={row.day} className="flex justify-between text-xs">
                    <span className="text-gray-500">{row.day}</span>
                    <strong className="text-gray-800">{row.users}</strong>
                  </div>
                ))}
                {(analytics?.daily_active_users || []).length === 0 && <p className="text-xs text-gray-400">No activity yet</p>}
              </div>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">Chats per user</h3>
              <div className="space-y-2 max-h-44 overflow-y-auto">
                {(analytics?.chats_per_user || []).slice(0, 8).map(row => (
                  <div key={row.email} className="flex justify-between gap-2 text-xs">
                    <span className="text-gray-500 truncate">{row.email}</span>
                    <strong className="text-gray-800">{row.chats}</strong>
                  </div>
                ))}
                {(analytics?.chats_per_user || []).length === 0 && <p className="text-xs text-gray-400">No chats yet</p>}
              </div>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">System health</h3>
              <InfoRow label="Threads" value={String(totals.threads || 0)} />
              <InfoRow label="Failed documents" value={String(totals.failed_documents || 0)} />
              <InfoRow label="Oldest pending request" value={`${queueAge} hours`} />
            </div>
          </div>
        </section>

        <section>
          <SectionTitle id="users" icon={Users} title="User Activity and Details" description="Approve users and review account usage" />
          <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search by email..."
                className="w-full pl-8 pr-4 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100 bg-white"
              />
            </div>
            <div className="flex bg-white border border-gray-200 rounded-xl overflow-hidden">
              {[['all', 'All'], ['pending', 'Pending'], ['approved', 'Approved']].map(([val, label]) => (
                <button key={val} onClick={() => setFilter(val)}
                  className={`px-4 py-2 text-xs font-semibold transition ${filter === val ? 'bg-primary-500 text-white' : 'text-gray-500 hover:bg-gray-50'}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 overflow-x-auto">
            {loading ? (
              <div className="py-16 flex flex-col items-center gap-3 text-gray-400">
                <RefreshCw size={20} className="animate-spin" />
                <p className="text-sm">Loading admin data...</p>
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="py-16 text-center">
                <Users size={28} className="text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-400">No users found</p>
              </div>
            ) : (
              <table className="w-full min-w-[760px]">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-semibold text-gray-400 px-5 py-3">User</th>
                    <th className="text-left text-xs font-semibold text-gray-400 px-3 py-3">Status</th>
                    <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Chats used</th>
                    <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Joined</th>
                    <th className="text-right text-xs font-semibold text-gray-400 px-5 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(user => {
                    const isActing = actionEmail === user.email
                    return (
                      <tr key={user.email} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                              <span className="text-xs font-bold text-primary-600">{user.email[0].toUpperCase()}</span>
                            </div>
                            <span className="text-sm text-gray-700 font-medium truncate">{user.email}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3.5">
                          <Badge approved={user.is_approved} isAdmin={user.is_admin} verified={user.is_verified} />
                        </td>
                        <td className="px-3 py-3.5 text-right">
                          <span className={`text-sm font-semibold ${user.is_approved ? 'text-green-600' : user.chat_count >= 5 ? 'text-red-500' : 'text-gray-700'}`}>
                            {user.chat_count}
                            {!user.is_approved && <span className="text-gray-400 font-normal">/5</span>}
                          </span>
                        </td>
                        <td className="px-3 py-3.5 text-right text-xs text-gray-400">{shortDate(user.created_at)}</td>
                        <td className="px-5 py-3.5 text-right">
                          {isActing ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                              <RefreshCw size={12} className="animate-spin" /> Working...
                            </span>
                          ) : user.is_approved ? (
                            <button onClick={() => handleRevoke(user.email)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 transition">
                              <X size={12} /> Revoke
                            </button>
                          ) : (
                            <button onClick={() => handleApprove(user.email)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-green-700 bg-green-50 hover:bg-green-100 border border-green-200 transition">
                              <Check size={12} /> Approve
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section>
          <SectionTitle id="chat-history" icon={History} title="Chat History Management" description="Recent threads across all users" />
          <div className="bg-white rounded-xl border border-gray-100 overflow-x-auto">
            <table className="w-full min-w-[820px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-xs font-semibold text-gray-400 px-5 py-3">Thread</th>
                  <th className="text-left text-xs font-semibold text-gray-400 px-3 py-3">Owner</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Messages</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Updated</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-5 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {threads.slice(0, 12).map(thread => (
                  <tr key={thread.thread_id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                    <td className="px-5 py-3.5">
                      <p className="text-sm font-semibold text-gray-700 truncate max-w-xs">{thread.title || 'Untitled chat'}</p>
                      <p className="text-[10px] text-gray-400 truncate">{thread.thread_id}</p>
                    </td>
                    <td className="px-3 py-3.5 text-xs text-gray-500 truncate">{thread.user_id || '-'}</td>
                    <td className="px-3 py-3.5 text-right text-sm font-semibold text-gray-700">{thread.message_count || 0}</td>
                    <td className="px-3 py-3.5 text-right text-xs text-gray-400">{shortDate(thread.updated_at || thread.last_message_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button onClick={() => handleDeleteThread(thread)} disabled={actionThread === thread.thread_id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 disabled:opacity-50">
                        {actionThread === thread.thread_id ? <RefreshCw size={12} className="animate-spin" /> : <Trash2 size={12} />} Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {!threads.length && (
                  <tr><td colSpan="5" className="px-5 py-10 text-center text-sm text-gray-400">No chat threads found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <SectionTitle id="library" icon={FolderOpen} title="File and Library Management" description="Uploaded document inventory and indexing status" />
          <div className="bg-white rounded-xl border border-gray-100 overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-xs font-semibold text-gray-400 px-5 py-3">Document</th>
                  <th className="text-left text-xs font-semibold text-gray-400 px-3 py-3">Owner</th>
                  <th className="text-left text-xs font-semibold text-gray-400 px-3 py-3">Status</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Chunks</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-3 py-3">Uploaded</th>
                  <th className="text-right text-xs font-semibold text-gray-400 px-5 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.slice(0, 12).map(doc => (
                  <tr key={doc.doc_id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                    <td className="px-5 py-3.5">
                      <p className="text-sm font-semibold text-gray-700 truncate max-w-xs">{doc.filename}</p>
                      <p className="text-[10px] text-gray-400 truncate">{doc.workspace_name || doc.workspace_id || 'No workspace'}</p>
                    </td>
                    <td className="px-3 py-3.5 text-xs text-gray-500 truncate">{doc.user_id || '-'}</td>
                    <td className="px-3 py-3.5">
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${doc.status === 'failed' ? 'bg-red-100 text-red-600' : doc.status === 'indexed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-3 py-3.5 text-right text-sm font-semibold text-gray-700">{doc.chunk_count || 0}</td>
                    <td className="px-3 py-3.5 text-right text-xs text-gray-400">{shortDate(doc.uploaded_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button onClick={() => handleDeleteDocument(doc)} disabled={actionDoc === doc.doc_id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 disabled:opacity-50">
                        {actionDoc === doc.doc_id ? <RefreshCw size={12} className="animate-spin" /> : <Trash2 size={12} />} Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {!documents.length && (
                  <tr><td colSpan="6" className="px-5 py-10 text-center text-sm text-gray-400">No uploaded documents found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <SectionTitle id="settings" icon={Settings} title="Settings and Chatbot Controls" description="Current feature switches and operational controls" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">Chatbot Features</h3>
              <div className="flex flex-wrap gap-2">
                <StatusPill label="Mistral chat model" />
                <StatusPill label="LangGraph memory" />
                <StatusPill label="Web search" />
                <StatusPill label="Wikipedia" />
                <StatusPill label="Calculator" />
                <StatusPill label="Document RAG" />
                <button onClick={() => { window.history.replaceState({}, '', `#mcp`); scrollToSection('mcp'); }} className="px-3 py-2 rounded-lg text-xs font-semibold text-gray-500 hover:bg-gray-50 hover:text-gray-800 whitespace-nowrap">
                  MCP Integrations
                </button>
                <StatusPill label="Share links" />
              </div>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">Management Controls</h3>
              <InfoRow label="User access" value="Approve or revoke from Users section" />
              <InfoRow label="Chat history" value="Delete recent threads from Chat History" />
              <InfoRow label="File library" value="Delete uploaded documents from Library" />
              <InfoRow label="Analytics refresh" value="Use Refresh in the header" />
            </div>
          </div>
        </section>

        <section>
          <SectionTitle id="mcp" icon={Settings} title="MCP Integrations" description="Manage connections to external services like Gmail, LinkedIn, and more." />
          <div className="grid grid-cols-1 gap-4">
            <ManagementTile icon={Mail} title="Gmail" description="Connect to Gmail to read and send emails." meta="Manage your mailbox" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={Users} title="LinkedIn" description="Connect to LinkedIn to access your profile and network." meta="Professional network" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={FolderOpen} title="Google Drive" description="Connect to Google Drive to access your files." meta="File storage" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={Activity} title="YouTube" description="Connect to YouTube to manage your videos and channel." meta="Video platform" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={Bot} title="Telegram" description="Connect to Telegram to send and receive messages." meta="Messaging app" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={Database} title="Notion" description="Connect to Notion to access your workspace and databases." meta="All-in-one workspace" onClick={() => {/* TODO: Implement connect */}} />
            <ManagementTile icon={Users} title="Trello" description="Connect to Trello to manage your boards and cards." meta="Project management" onClick={() => {/* TODO: Implement connect */}} />
          </div>
        </section>
      </main>
    </div>
  )
}

function LayoutDashboardIcon(props) {
  return <Database {...props} />
}
