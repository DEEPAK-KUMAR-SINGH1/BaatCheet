import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { v4 as uuidv4 } from 'uuid'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Bot,
  Database,
  FolderOpen,
  Link,
  Mail,
  RefreshCw,
  Settings,
  Square,
  Unplug,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth.jsx'
import Sidebar from '../components/Sidebar'
import MessageBubble from '../components/MessageBubble'
import ChatInput from '../components/ChatInput'
import DocPanel from '../components/DocPanel'
import {
  attachThreadWorkspace,
  createThread,
  createWorkspace,
  connectGmail,
  disconnectGmail,
  editMessage,
  getConnectorConnections,
  getSourceChunk,
  getThreadMessages,
  getThreads,
  getWorkspaces,
  getWorkspaceDocs,
  regenerateThread,
  revokeThreadShare,
  searchConversations,
  shareThread,
  streamChat,
  connectLinkedin,
  disconnectLinkedin,
  connectGoogleDrive,
  disconnectGoogleDrive,
  connectYoutube,
  disconnectYoutube,
  connectTelegram,
  disconnectTelegram,
  connectNotion,
  disconnectNotion,
  connectTrello,
  disconnectTrello,
  connectConnectorWithToken,
} from '../api/client.jsx'

const CONNECTOR_SETUP_STATUSES = new Set(['needs_credentials', 'needs_dependencies'])

const CONNECTOR_SERVICES = [
  { app: 'gmail', name: 'Gmail', auth: 'Google OAuth', icon: Mail, connect: connectGmail, disconnect: disconnectGmail },
  { app: 'linkedin', name: 'LinkedIn', auth: 'LinkedIn OAuth', icon: Users, connect: connectLinkedin, disconnect: disconnectLinkedin },
  { app: 'google_drive', name: 'Google Drive', auth: 'Google OAuth', icon: FolderOpen, connect: connectGoogleDrive, disconnect: disconnectGoogleDrive },
  { app: 'youtube', name: 'YouTube', auth: 'Google OAuth', icon: Activity, connect: connectYoutube, disconnect: disconnectYoutube },
  { app: 'telegram', name: 'Telegram', auth: 'Bot token', icon: Bot, connect: connectTelegram, disconnect: disconnectTelegram },
  { app: 'notion', name: 'Notion', auth: 'Notion OAuth', icon: Database, connect: connectNotion, disconnect: disconnectNotion },
  { app: 'trello', name: 'Trello', auth: 'Trello token', icon: Users, connect: connectTrello, disconnect: disconnectTrello },
]

function connectorServiceName(app) {
  return CONNECTOR_SERVICES.find(service => service.app === app)?.name || app
}

export default function ChatPage() {
  const { isAdmin, isApproved, chatCount, refreshStats } = useAuth()
  const navigate = useNavigate()

  const [threads, setThreads] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [workspaces, setWorkspaces] = useState([])
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null)
  const [docs, setDocs] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [limitReached, setLimitReached] = useState(false)
  const [selectedSource, setSelectedSource] = useState(null)
  const [sourceDetail, setSourceDetail] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [shareInfo, setShareInfo] = useState(null)
  const [connectorConnections, setConnectorConnections] = useState([])
  const [connectorLoadingApp, setConnectorLoadingApp] = useState('')
  const [connectorNotice, setConnectorNotice] = useState('')
  const [connectorsOpen, setConnectorsOpen] = useState(false)
  const connectorsButtonRef = useRef(null)
  const bottomRef = useRef()
  const scrollAreaRef = useRef(null)
  const stickToBottomRef = useRef(true)
  const abortRef = useRef(null)

  const activeWorkspace = workspaces.find(w => w.workspace_id === activeWorkspaceId) || null
  const connectorServices = CONNECTOR_SERVICES.map(service => {
    const connection = connectorConnections.find(item => item.app === service.app)
    const connected = Boolean(connection?.connected)
    return {
      ...service,
      connection,
      connected,
      needsSetup: CONNECTOR_SETUP_STATUSES.has(connection?.status),
      loading: connectorLoadingApp === service.app,
    }
  })
  const connectedConnectorCount = connectorServices.filter(service => service.connected).length

  const isNearBottom = useCallback(() => {
    const el = scrollAreaRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 160
  }, [])

  const scrollToBottom = useCallback((behavior = 'auto') => {
    requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ behavior, block: 'end' })
    })
  }, [])

  const keepBottomIfNeeded = useCallback((behavior = 'auto') => {
    if (stickToBottomRef.current) scrollToBottom(behavior)
  }, [scrollToBottom])

  const handleScrollArea = useCallback(() => {
    stickToBottomRef.current = isNearBottom()
  }, [isNearBottom])

  const upsertConnectorConnection = (connection) => {
    if (!connection?.app) return
    setConnectorConnections(prev => {
      const withoutApp = prev.filter(c => c.app !== connection.app)
      return [connection, ...withoutApp]
    })
  }

  const refreshConnectorConnections = useCallback(async () => {
    try {
      const data = await getConnectorConnections()
      setConnectorConnections(data.connections || [])
    } catch {
      setConnectorConnections([])
    }
  }, [])

  useEffect(() => {
    initChat()
    refreshConnectorConnections()
  }, [refreshConnectorConnections])

  useEffect(() => {
    const onFocus = () => refreshConnectorConnections()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refreshConnectorConnections])

  useEffect(() => {
    let cancelled = false
    const params = new URLSearchParams(window.location.search)
    const app = params.get('connector')
    if (!app) return

    const status = params.get('status')
    const detail = params.get('detail')
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    const name = connectorServiceName(app)
    const cleanupUrl = () => {
      params.delete('connector')
      params.delete('status')
      params.delete('detail')
      params.delete('state')
      params.delete('token')
      const nextHash = hashParams.has('token') ? '' : window.location.hash
      const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}${nextHash}`
      window.history.replaceState({}, '', next)
    }

    const completeConnection = async () => {
      if (app === 'trello' && status === 'token') {
        const token = params.get('token') || hashParams.get('token')
        if (!token) {
          setConnectorNotice('Trello did not return an authorization token.')
          cleanupUrl()
          return
        }
        try {
          const connection = await connectConnectorWithToken('trello', token, { state: params.get('state') })
          if (!cancelled) {
            upsertConnectorConnection(connection)
            setConnectorNotice('Trello connected.')
          }
        } catch (err) {
          if (!cancelled) setConnectorNotice(err.message || 'Trello connection failed.')
        } finally {
          refreshConnectorConnections()
          cleanupUrl()
        }
        return
      }

      setConnectorNotice(
        status === 'connected'
          ? `${name} connected.`
          : detail || `${name} connection failed.`
      )
      refreshConnectorConnections()
      cleanupUrl()
    }

    completeConnection()
    return () => { cancelled = true }
  }, [refreshConnectorConnections])

  useEffect(() => {
    if (!isAdmin && !isApproved && chatCount >= 5) setLimitReached(true)
  }, [isAdmin, isApproved, chatCount])

  useEffect(() => {
    if (!messages.length) return
    keepBottomIfNeeded(streaming ? 'auto' : 'smooth')
  }, [messages.length, streaming, keepBottomIfNeeded])

  useEffect(() => {
    const run = async () => {
      if (!searchQuery.trim()) {
        setSearchResults([])
        return
      }
      try {
        setSearchResults(await searchConversations(searchQuery.trim()))
      } catch {
        setSearchResults([])
      }
    }
    const id = setTimeout(run, 250)
    return () => clearTimeout(id)
  }, [searchQuery])

  const refreshWorkspaces = async () => {
    try {
      const list = await getWorkspaces()
      setWorkspaces(list)
      return list
    } catch {
      return []
    }
  }

  const refreshDocs = async (workspaceId) => {
    if (!workspaceId) {
      setDocs([])
      return
    }
    try {
      setDocs(await getWorkspaceDocs(workspaceId))
    } catch {
      setDocs([])
    }
  }

  const initChat = async () => {
    const [threadList, workspaceList] = await Promise.all([
      getThreads().catch(() => []),
      getWorkspaces().catch(() => []),
    ])
    setThreads(threadList)
    setWorkspaces(workspaceList)
    if (threadList.length > 0) loadThread(threadList[0].thread_id, threadList)
    else startNewChat(threadList)
  }

  const loadThread = async (tid, threadList = threads) => {
    stickToBottomRef.current = true
    setActiveId(tid)
    setMessages([])
    setDocs([])
    setSelectedSource(null)
    setSourceDetail(null)
    setSelectedDoc(null)
    setShareInfo(null)
    setLimitReached(false)
    try {
      const thread = threadList.find(t => t.thread_id === tid)
      const workspaceId = thread?.workspace_id || null
      setActiveWorkspaceId(workspaceId)
      const [msgs] = await Promise.all([
        getThreadMessages(tid),
        refreshDocs(workspaceId),
      ])
      setMessages(msgs)
    } catch {}
  }

  const startNewChat = async (threadList = threads) => {
    const newId = uuidv4()
    try {
      stickToBottomRef.current = true
      await createThread(newId)
      const updated = [{ thread_id: newId, title: 'New Chat', workspace_id: null, created_at: '', updated_at: '' }, ...threadList]
      setThreads(updated)
      setActiveId(newId)
      setActiveWorkspaceId(null)
      setMessages([])
      setDocs([])
      setSelectedSource(null)
      setSourceDetail(null)
      setSelectedDoc(null)
      setLimitReached(false)
    } catch {}
  }

  const handleDeleted = async (tid) => {
    const updated = threads.filter(t => t.thread_id !== tid)
    setThreads(updated)
    if (activeId === tid) {
      if (updated.length > 0) loadThread(updated[0].thread_id, updated)
      else startNewChat([])
    }
  }

  const handleRenamed = (tid, title) => {
    setThreads(prev => prev.map(t => t.thread_id === tid ? { ...t, title } : t))
  }

  const updateThreadTitle = (tid, firstMsg) => {
    const title = firstMsg.slice(0, 50) + (firstMsg.length > 50 ? '...' : '')
    setThreads(prev => prev.map(t => t.thread_id === tid ? { ...t, title } : t))
  }

  const handleWorkspaceChange = async (workspaceId) => {
    if (!activeId) return
    try {
      await attachThreadWorkspace(activeId, workspaceId)
      setActiveWorkspaceId(workspaceId)
      setThreads(prev => prev.map(t => t.thread_id === activeId ? { ...t, workspace_id: workspaceId } : t))
      refreshDocs(workspaceId)
    } catch {}
  }

  const handleCreateWorkspace = async () => {
    const name = window.prompt('Workspace name', 'Knowledge Workspace')
    if (!name) return
    try {
      const workspace = await createWorkspace(name)
      const list = await refreshWorkspaces()
      setWorkspaces(list.length ? list : [workspace])
      await handleWorkspaceChange(workspace.workspace_id)
    } catch {}
  }

  const handleConnectorConnect = async (service) => {
    setConnectorLoadingApp(service.app)
    setConnectorNotice('')
    try {
      const data = await service.connect()
      if (!data.auth_url) throw new Error(`${service.name} did not return an authorization URL.`)
      window.location.assign(data.auth_url)
    } catch (err) {
      setConnectorNotice(err.message || `Could not start ${service.name} connection.`)
      refreshConnectorConnections()
    } finally {
      setConnectorLoadingApp('')
    }
  }

  const handleConnectorDisconnect = async (service) => {
    setConnectorLoadingApp(service.app)
    setConnectorNotice('')
    try {
      const data = await service.disconnect()
      upsertConnectorConnection(data)
      setConnectorNotice(`${service.name} disconnected.`)
    } catch (err) {
      setConnectorNotice(err.message || `Could not disconnect ${service.name}.`)
    } finally {
      setConnectorLoadingApp('')
    }
  }

  const handleFileUploaded = async (docRecord) => {
    if (!activeWorkspaceId && docRecord.workspace_id) {
      setActiveWorkspaceId(docRecord.workspace_id)
      setThreads(prev => prev.map(t => t.thread_id === activeId ? { ...t, workspace_id: docRecord.workspace_id } : t))
    }
    setDocs(prev => {
      const exists = prev.some(d => d.doc_id === docRecord.doc_id)
      return exists ? prev.map(d => d.doc_id === docRecord.doc_id ? docRecord : d) : [...prev, docRecord]
    })
    refreshWorkspaces()
  }

  const runStream = useCallback(async ({ mode, text }) => {
    if (!activeId || streaming) return
    if (!isAdmin && !isApproved && chatCount >= 5 && mode === 'send') {
      setLimitReached(true)
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    stickToBottomRef.current = true
    setStreaming(true)

    if (mode === 'send') {
      const userMsg = { id: `temp-u-${Date.now()}`, role: 'user', content: text, metadata: {}, status: 'complete' }
      const assistantMsg = { id: `temp-a-${Date.now()}`, role: 'assistant', content: '', metadata: {}, status: 'complete' }
      setMessages(prev => {
        if (prev.length === 0) updateThreadTitle(activeId, text)
        return [...prev, userMsg, assistantMsg]
      })
    } else {
      setMessages(prev => {
        const trimmed = [...prev]
        while (trimmed.length && trimmed[trimmed.length - 1].role === 'assistant') trimmed.pop()
        return [...trimmed, { id: `temp-a-${Date.now()}`, role: 'assistant', content: '', metadata: {}, status: 'complete' }]
      })
    }

    let full = ''
    let sources = []
    let rendered = ''
    let renderFrame = null
    const applyAssistantContent = (nextContent) => {
      setMessages(prev => {
        if (!prev.length) return prev
        const updated = [...prev]
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: nextContent }
        return updated
      })
      keepBottomIfNeeded('auto')
    }
    const scheduleAssistantContent = () => {
      if (renderFrame != null) return
      renderFrame = requestAnimationFrame(() => {
        renderFrame = null
        if (rendered === full) return
        rendered = full
        applyAssistantContent(rendered)
      })
    }
    const flushAssistantContent = () => {
      if (renderFrame != null) {
        cancelAnimationFrame(renderFrame)
        renderFrame = null
      }
      if (rendered === full) return
      rendered = full
      applyAssistantContent(rendered)
    }

    try {
      const iterator = mode === 'send'
        ? streamChat(activeId, text, activeWorkspaceId, controller.signal)
        : regenerateThread(activeId, activeWorkspaceId, controller.signal)

      for await (const event of iterator) {
        if (event.type === 'token') {
          full += event.text
          scheduleAssistantContent()
        } else if (event.type === 'sources') {
          flushAssistantContent()
          sources = event.sources || []
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              metadata: { ...(updated[updated.length - 1].metadata || {}), sources },
            }
            return updated
          })
          keepBottomIfNeeded('auto')
        } else if (event.type === 'error') {
          throw new Error(event.error)
        }
      }
      flushAssistantContent()
      refreshStats()
      const [list, persisted] = await Promise.all([getThreads(), getThreadMessages(activeId)])
      setThreads(list)
      setMessages(persisted)
    } catch (err) {
      flushAssistantContent()
      if (err.name === 'AbortError') {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...updated[updated.length - 1], status: 'stopped' }
          return updated
        })
      } else if (err.status === 403) {
        setLimitReached(true)
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: err.message, metadata: {}, status: 'failed' }
          return updated
        })
      } else {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: `Error: ${err.message}`, metadata: {}, status: 'failed' }
          return updated
        })
      }
    } finally {
      if (renderFrame != null) cancelAnimationFrame(renderFrame)
      setStreaming(false)
      abortRef.current = null
    }
  }, [activeId, activeWorkspaceId, streaming, isAdmin, isApproved, chatCount, refreshStats, keepBottomIfNeeded])

  const handleSend = (text) => runStream({ mode: 'send', text })

  const handleRegenerate = () => runStream({ mode: 'regenerate' })

  const handleStop = () => {
    abortRef.current?.abort()
  }

  const handleEdit = async (msg) => {
    const next = window.prompt('Edit your last message', msg.content)
    if (!next || next.trim() === msg.content) return
    try {
      const updated = await editMessage(activeId, msg.id, next.trim())
      setMessages(updated)
      runStream({ mode: 'regenerate' })
    } catch (err) {
      alert(err.message)
    }
  }

  const handleSourceClick = async (source) => {
    setSelectedSource(source)
    setSourceDetail(null)
    try {
      setSourceDetail(await getSourceChunk(source.doc_id, source.chunk_index))
    } catch {
      setSourceDetail({ content: source.snippet, filename: source.filename, page: source.page })
    }
  }

  const handleShare = async () => {
    if (!activeId) return
    try {
      const info = await shareThread(activeId)
      setShareInfo(info)
      await navigator.clipboard?.writeText(`${window.location.origin}${info.url}`)
    } catch (err) {
      alert(err.message)
    }
  }

  const handleUnshare = async () => {
    if (!activeId) return
    await revokeThreadShare(activeId)
    setShareInfo(null)
  }

  const hasMessages = messages.length > 0
  const chatDisabled = streaming || limitReached
  const latestUserIndex = messages.map(m => m.role).lastIndexOf('user')
  const latestAssistantIndex = messages.map(m => m.role).lastIndexOf('assistant')

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gray-50">
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={(tid) => loadThread(tid)}
        onNew={() => startNewChat()}
        onDeleted={handleDeleted}
        onRenamed={handleRenamed}
        onAdminClick={(section) => navigate(section ? `/admin#${section}` : '/admin')}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchResults={searchResults}
      />

      <div className="flex-1 flex min-w-0 h-full">
        <div className="flex-1 flex flex-col min-w-0 h-full">
          {limitReached && (
            <div className="bg-red-50 border-b border-red-200 px-4 py-3 flex items-center gap-3">
              <AlertTriangle size={16} className="text-red-500 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-red-700">Chat limit reached (5/5)</p>
                <p className="text-xs text-red-500">Contact admin for unlimited access.</p>
              </div>
            </div>
          )}

          {!limitReached && !isAdmin && !isApproved && chatCount > 0 && chatCount < 5 && (
            <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center gap-2">
              <span className="text-xs text-yellow-700">
                Free plan: <strong>{5 - chatCount} chats remaining</strong>. Contact admin for unlimited access.
              </span>
            </div>
          )}

          <div className="px-4 py-2 border-b border-gray-100 bg-white flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500 flex-1 min-w-[220px] truncate">
              Hybrid mode: documents, web search, Wikipedia, calculator, and connected apps can work together.
            </span>
            <button ref={connectorsButtonRef} onClick={() => setConnectorsOpen(open => !open)} title="Connectors"
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition
                ${connectorsOpen
                  ? 'bg-primary-50 text-primary-700 border-primary-100'
                  : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-primary-50 hover:text-primary-700 hover:border-primary-100'}`}>
              <Settings size={12} /> Connectors
              {connectedConnectorCount > 0 && (
                <span className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-100 px-1 text-[10px] font-bold text-emerald-700">
                  {connectedConnectorCount}
                </span>
              )}
            </button>
            {streaming && (
              <button onClick={handleStop}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 text-amber-700 border border-amber-200 text-xs font-semibold">
                <Square size={12} /> Stop
              </button>
            )}
            <button onClick={handleShare} disabled={!activeId}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-50 text-primary-700 border border-primary-100 text-xs font-semibold disabled:opacity-50">
              <Link size={12} /> Share
            </button>
          </div>

          {connectorNotice && (
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 flex items-center gap-2 text-xs text-gray-600">
              <span className="flex-1 truncate">{connectorNotice}</span>
              <button onClick={() => setConnectorNotice('')} className="p-1 rounded-lg text-gray-400 hover:bg-white">
                <X size={13} />
              </button>
            </div>
          )}

          {shareInfo?.url && (
            <div className="px-4 py-2 bg-primary-50 border-b border-primary-100 flex items-center gap-2 text-xs text-primary-700">
              <span className="flex-1 truncate">Share link copied: {window.location.origin}{shareInfo.url}</span>
              <button onClick={handleUnshare} className="font-semibold hover:underline">Revoke</button>
            </div>
          )}

          <DocPanel
            docs={docs}
            onDocsChange={setDocs}
            workspace={activeWorkspace}
            workspaces={workspaces}
            onWorkspaceChange={handleWorkspaceChange}
            onCreateWorkspace={handleCreateWorkspace}
            selectedDoc={selectedDoc}
            onPreviewDoc={setSelectedDoc}
          />

          <div ref={scrollAreaRef} onScroll={handleScrollArea} className="flex-1 overflow-y-auto">
            {!hasMessages ? (
              <div className="h-full flex flex-col items-center justify-center gap-4 px-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center shadow-lg">
                  <Bot size={32} className="text-white" />
                </div>
                <div className="text-center">
                  <h2 className="text-xl font-bold text-gray-800 mb-1">How can I help you today?</h2>
                  <p className="text-sm text-gray-500 max-w-sm">
                    Ask anything, upload documents, or reuse a workspace across multiple chats.
                  </p>
                </div>
                {!limitReached && (
                  <div className="flex flex-wrap justify-center gap-2 max-w-lg mt-2">
                    {['Latest tech news', 'Calculate 15% of 2450', 'Summarize my uploaded documents', 'Compare this file with current web info'].map(s => (
                      <button key={s} onClick={() => handleSend(s)}
                        className="px-4 py-2 bg-white border border-gray-200 rounded-xl text-sm text-gray-600
                                   hover:border-primary-300 hover:text-primary-600 hover:bg-primary-50 transition shadow-sm">
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="max-w-3xl mx-auto px-4 py-6">
                {messages.map((msg, i) => (
                  <MessageBubble key={msg.id || i}
                    role={msg.role}
                    content={msg.content}
                    metadata={msg.metadata}
                    status={msg.status}
                    isStreaming={streaming && i === messages.length - 1 && msg.role === 'assistant'}
                    canEdit={!streaming && i === latestUserIndex && msg.role === 'user'}
                    canRegenerate={!streaming && i === latestAssistantIndex && msg.role === 'assistant'}
                    onEdit={() => handleEdit(msg)}
                    onRegenerate={handleRegenerate}
                    onSourceClick={handleSourceClick}
                  />
                ))}
                <div ref={bottomRef} />
              </div>
            )}
          </div>

          <div className="border-t border-gray-100 bg-white">
            <ChatInput
              threadId={activeId}
              workspaceId={activeWorkspaceId}
              disabled={chatDisabled}
              limitReached={limitReached}
              onSend={handleSend}
              onFileUploaded={handleFileUploaded}
            />
          </div>
        </div>

        {(selectedSource || sourceDetail) && (
          <aside className="w-80 border-l border-gray-100 bg-white h-full flex flex-col">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
              <div>
                <p className="text-sm font-bold text-gray-800">View source</p>
                <p className="text-xs text-gray-400 truncate max-w-[220px]">
                  {sourceDetail?.filename || selectedSource?.filename}
                </p>
              </div>
              <button onClick={() => { setSelectedSource(null); setSourceDetail(null) }}
                className="ml-auto p-1.5 rounded-lg text-gray-400 hover:bg-gray-50">
                <X size={15} />
              </button>
            </div>
            <div className="p-4 overflow-y-auto text-sm text-gray-700">
              <div className="mb-3 flex flex-wrap gap-2 text-xs">
                {selectedSource?.page && <span className="px-2 py-1 rounded-lg bg-gray-100">Page {selectedSource.page}</span>}
                {selectedSource?.chunk_index != null && <span className="px-2 py-1 rounded-lg bg-gray-100">Chunk {selectedSource.chunk_index}</span>}
                {selectedSource?.score != null && <span className="px-2 py-1 rounded-lg bg-gray-100">Score {Number(selectedSource.score).toFixed(3)}</span>}
              </div>
              <p className="whitespace-pre-wrap leading-relaxed">
                {sourceDetail?.content || selectedSource?.snippet || 'Loading source...'}
              </p>
            </div>
          </aside>
        )}
        {connectorsOpen && <ConnectorsPortal
          open={connectorsOpen}
          anchorRef={connectorsButtonRef}
          services={connectorServices}
          loadingApp={connectorLoadingApp}
          onConnect={handleConnectorConnect}
          onDisconnect={handleConnectorDisconnect}
          onRefresh={refreshConnectorConnections}
          onClose={() => setConnectorsOpen(false)}
        />}
      </div>
    </div>
  )
  }

function ConnectorsPortal({
  open,
  anchorRef,
  services,
  loadingApp,
  onConnect,
  onDisconnect,
  onRefresh,
  onClose,
}) {
  const portalRef = useRef(null)
  const [position, setPosition] = useState({ left: 0, top: 0 })

  useEffect(() => {
    if (!open) return

    const updatePosition = () => {
      const rect = anchorRef.current?.getBoundingClientRect()
      if (!rect) return

      const gap = 10
      const width = Math.min(380, window.innerWidth - 24)
      const height = Math.min(560, window.innerHeight - 24)
      let left = rect.right + gap
      if (left + width > window.innerWidth - 12) left = rect.right - width
      left = Math.max(12, Math.min(left, window.innerWidth - width - 12))

      let top = rect.bottom + gap
      if (top + height > window.innerHeight - 12) top = rect.top - height - gap
      top = Math.max(12, Math.min(top, window.innerHeight - height - 12))

      setPosition({ left, top })
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

  const connectedCount = services.filter(service => service.connected).length

  return createPortal(
    <div
      ref={portalRef}
      className="connectors-portal fixed z-50 w-[min(380px,calc(100vw-24px))] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl"
      style={{ left: position.left, top: position.top }}
    >
      <div className="border-b border-gray-100 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-700">
            <Settings size={17} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold text-gray-800">Connectors</h3>
            <p className="text-xs text-gray-400">{connectedCount}/{services.length} connected</p>
          </div>
          <button onClick={onRefresh} disabled={Boolean(loadingApp)} title="Refresh connector status"
            className="flex h-8 w-8 items-center justify-center rounded-xl text-gray-400 hover:bg-gray-50 hover:text-gray-700 disabled:opacity-50">
            <RefreshCw size={14} />
          </button>
          <button onClick={onClose} title="Close connectors"
            className="flex h-8 w-8 items-center justify-center rounded-xl text-gray-400 hover:bg-gray-50 hover:text-gray-700">
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="max-h-[min(68vh,520px)] space-y-2 overflow-y-auto p-2">
        {services.map(service => (
          <ConnectorServiceCard
            key={service.app}
            service={service}
            loadingApp={loadingApp}
            onConnect={onConnect}
            onDisconnect={onDisconnect}
          />
        ))}
      </div>
    </div>,
    document.body,
  )
}

function ConnectorServiceCard({ service, loadingApp, onConnect, onDisconnect }) {
  const Icon = service.icon
  const busy = Boolean(loadingApp)
  const status = getConnectorStatus(service)
  const message = service.connection?.message || `Connect with ${service.auth}.`
  const capabilityLabel = formatConnectorCapabilities(service.connection?.capabilities)
  const header = (
    <>
      <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${service.connected ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-50 text-gray-500'}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0 flex-1 text-left">
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate text-sm font-semibold text-gray-800">{service.name}</p>
          <ConnectorStatusPill status={status} />
        </div>
        <p className="mt-0.5 truncate text-xs text-gray-400">{message}</p>
        <p className="mt-0.5 text-[11px] font-semibold text-gray-400">{service.auth}</p>
      </div>
    </>
  )

  return (
    <div className={`rounded-xl border transition ${service.connected ? 'border-emerald-100 bg-emerald-50/40' : 'border-gray-100 bg-white hover:border-primary-100 hover:bg-primary-50/30'}`}>
      {service.connected ? (
        <div className="flex w-full items-center gap-3 px-3 pt-3">
          {header}
        </div>
      ) : (
        <button type="button" onClick={() => onConnect(service)} disabled={busy}
          title={message}
          className="flex w-full items-center gap-3 px-3 pt-3 disabled:cursor-not-allowed disabled:opacity-60">
          {header}
        </button>
      )}

      <div className="flex items-center gap-2 px-3 pb-3 pt-2">
        <p className="min-w-0 flex-1 truncate text-[11px] text-gray-400">{capabilityLabel}</p>
        {service.connected ? (
          <button type="button" onClick={() => onDisconnect(service)} disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-100 bg-white px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50">
            <Unplug size={12} /> Disconnect
          </button>
        ) : (
          <button type="button" onClick={() => onConnect(service)} disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-primary-100 bg-white px-2.5 py-1.5 text-xs font-semibold text-primary-700 hover:bg-primary-50 disabled:opacity-50">
            {service.loading ? 'Connecting...' : service.needsSetup ? 'Setup' : 'Connect'}
          </button>
        )}
      </div>
    </div>
  )
}

function ConnectorStatusPill({ status }) {
  return (
    <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${status.className}`}>
      {status.label}
    </span>
  )
}

function getConnectorStatus(service) {
  if (service.connected) {
    return { label: 'Connected', className: 'bg-emerald-100 text-emerald-800' }
  }
  if (service.needsSetup) {
    return { label: 'Setup needed', className: 'bg-amber-100 text-amber-800' }
  }
  return { label: 'Not connected', className: 'bg-gray-100 text-gray-600' }
}

function formatConnectorCapabilities(capabilities) {
  if (!capabilities?.length) return 'Ready for chat tools'
  return capabilities
    .slice(0, 3)
    .map(item => item.replaceAll('_', ' '))
    .join(', ')
}
