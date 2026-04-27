import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import { adminGetUsers, adminApproveUser, adminRevokeUser } from '../api/client.jsx'
import {
  ArrowLeft, Shield, Users, CheckCircle, Clock, RefreshCw,
  Search, Check, X, ChevronDown
} from 'lucide-react'

function StatCard({ label, value, color }) {
  const colors = {
    gray:   'bg-gray-50 border-gray-200 text-gray-700',
    green:  'bg-green-50 border-green-200 text-green-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    red:    'bg-red-50 border-red-200 text-red-600',
  }
  return (
    <div className={`border rounded-2xl px-5 py-4 flex flex-col gap-1 ${colors[color]}`}>
      <span className="text-2xl font-bold">{value}</span>
      <span className="text-xs font-medium opacity-70">{label}</span>
    </div>
  )
}

function Badge({ approved, isAdmin }) {
  if (isAdmin) return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-red-600">Admin</span>
  )
  if (approved) return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-green-700">Approved</span>
  )
  return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-yellow-100 text-yellow-700">Pending</span>
  )
}

export default function AdminPage() {
  const { isAdmin } = useAuth()
  const navigate    = useNavigate()

  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [search, setSearch]     = useState('')
  const [filter, setFilter]     = useState('all')  // all | pending | approved
  const [actionEmail, setActionEmail] = useState('')  // loading state per row

  useEffect(() => {
    if (!isAdmin) { navigate('/'); return }
    loadUsers()
  }, [isAdmin])

  const loadUsers = async () => {
    setLoading(true); setError('')
    try {
      const data = await adminGetUsers()
      setUsers(data)
    } catch (e) {
      setError('Failed to load users: ' + e.message)
    } finally { setLoading(false) }
  }

  const handleApprove = async (email) => {
    setActionEmail(email)
    try {
      await adminApproveUser(email)
      setUsers(prev => prev.map(u => u.email === email ? { ...u, is_approved: 1 } : u))
    } catch (e) { alert('Error: ' + e.message) }
    finally { setActionEmail('') }
  }

  const handleRevoke = async (email) => {
    setActionEmail(email)
    try {
      await adminRevokeUser(email)
      setUsers(prev => prev.map(u => u.email === email ? { ...u, is_approved: 0 } : u))
    } catch (e) { alert('Error: ' + e.message) }
    finally { setActionEmail('') }
  }

  // Stats
  const nonAdmins = users.filter(u => !u.is_admin)
  const approved  = nonAdmins.filter(u => u.is_approved).length
  const pending   = nonAdmins.filter(u => !u.is_approved).length

  // Filtered + searched list
  const filtered = users.filter(u => {
    if (u.is_admin) return false  // Admin ko list mein mat dikhao
    if (filter === 'approved' && !u.is_approved) return false
    if (filter === 'pending'  &&  u.is_approved) return false
    if (search && !u.email.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <button onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition">
          <ArrowLeft size={16} /> Back to Chat
        </button>
        <div className="flex-1 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-red-100 flex items-center justify-center">
            <Shield size={16} className="text-red-500" />
          </div>
          <div>
            <h1 className="font-bold text-gray-800 text-sm leading-tight">Admin Dashboard</h1>
            <p className="text-xs text-gray-400">Manage user access</p>
          </div>
        </div>
        <button onClick={loadUsers} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs text-gray-500 hover:bg-gray-100 transition">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-6">

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Total users" value={nonAdmins.length} color="gray" />
          <StatCard label="Approved (unlimited)" value={approved} color="green" />
          <StatCard label="Pending (5 chat limit)" value={pending} color="yellow" />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-3 mb-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by email..."
              className="w-full pl-8 pr-4 py-2 text-sm border border-gray-200 rounded-xl
                         focus:outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100 bg-white"
            />
          </div>

          {/* Filter tabs */}
          <div className="flex bg-white border border-gray-200 rounded-xl overflow-hidden">
            {[['all', 'All'], ['pending', 'Pending'], ['approved', 'Approved']].map(([val, label]) => (
              <button key={val} onClick={() => setFilter(val)}
                className={`px-4 py-2 text-xs font-semibold transition
                  ${filter === val ? 'bg-primary-500 text-white' : 'text-gray-500 hover:bg-gray-50'}`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          {loading ? (
            <div className="py-16 flex flex-col items-center gap-3 text-gray-400">
              <RefreshCw size={20} className="animate-spin" />
              <p className="text-sm">Loading users...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center">
              <Users size={28} className="text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No users found</p>
            </div>
          ) : (
            <table className="w-full">
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
                {filtered.map((user, i) => {
                  const isActing = actionEmail === user.email
                  return (
                    <tr key={user.email}
                      className={`border-b border-gray-50 last:border-0 hover:bg-gray-50 transition
                        ${i % 2 === 0 ? '' : 'bg-gray-50/40'}`}>

                      {/* Email */}
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                            <span className="text-xs font-bold text-primary-600">
                              {user.email[0].toUpperCase()}
                            </span>
                          </div>
                          <span className="text-sm text-gray-700 font-medium">{user.email}</span>
                        </div>
                      </td>

                      {/* Badge */}
                      <td className="px-3 py-3.5">
                        <Badge approved={user.is_approved} isAdmin={user.is_admin} />
                      </td>

                      {/* Chat count */}
                      <td className="px-3 py-3.5 text-right">
                        <span className={`text-sm font-semibold
                          ${user.is_approved ? 'text-green-600' : user.chat_count >= 5 ? 'text-red-500' : 'text-gray-700'}`}>
                          {user.chat_count}
                          {!user.is_approved && <span className="text-gray-400 font-normal">/5</span>}
                        </span>
                      </td>

                      {/* Date */}
                      <td className="px-3 py-3.5 text-right">
                        <span className="text-xs text-gray-400">
                          {user.created_at ? user.created_at.slice(0, 10) : '—'}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="px-5 py-3.5 text-right">
                        {isActing ? (
                          <div className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                            <RefreshCw size={12} className="animate-spin" /> Working...
                          </div>
                        ) : user.is_approved ? (
                          <button onClick={() => handleRevoke(user.email)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                                       text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 transition">
                            <X size={12} /> Revoke
                          </button>
                        ) : (
                          <button onClick={() => handleApprove(user.email)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                                       text-green-700 bg-green-50 hover:bg-green-100 border border-green-200 transition">
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

        <p className="text-center text-xs text-gray-400 mt-4">
          Approved users get unlimited chat access · Pending users have a 5-chat limit
        </p>
      </div>
    </div>
  )
}
