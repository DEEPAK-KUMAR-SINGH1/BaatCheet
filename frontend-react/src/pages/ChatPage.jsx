import { useState, useEffect, useRef, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'
import Sidebar from '../components/Sidebar'
import MessageBubble from '../components/MessageBubble'
import ChatInput from '../components/ChatInput'
import DocPanel from '../components/DocPanel'
import { Bot, AlertTriangle } from 'lucide-react'
import {
  getThreads, createThread, getThreadMessages,
  getDocs, streamChat, streamRagChat
} from '../api/client.jsx'

export default function ChatPage() {
  const { isAdmin, isApproved, chatCount, refreshStats } = useAuth()
  const navigate = useNavigate()

  const [threads, setThreads]             = useState([])
  const [activeId, setActiveId]           = useState(null)
  const [messages, setMessages]           = useState([])
  const [docs, setDocs]                   = useState([])
  const [streaming, setStreaming]         = useState(false)
  const [uploadingFile, setUploadingFile] = useState('')
  const [limitReached, setLimitReached]   = useState(false)
  const bottomRef = useRef()

  useEffect(() => { initChat() }, [])

  // Limit check on mount
  useEffect(() => {
    if (!isAdmin && !isApproved && chatCount >= 5) setLimitReached(true)
  }, [isAdmin, isApproved, chatCount])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const initChat = async () => {
    try {
      const list = await getThreads()
      setThreads(list)
      if (list.length > 0) loadThread(list[0].thread_id, list)
      else startNewChat(list)
    } catch { startNewChat([]) }
  }

  const loadThread = async (tid, threadList = threads) => {
    setActiveId(tid)
    setMessages([])
    setDocs([])
    setLimitReached(false)
    try {
      const [msgs, threadDocs] = await Promise.all([getThreadMessages(tid), getDocs(tid)])
      setMessages(msgs.map(m => ({ role: m.role, content: m.content })))
      setDocs(threadDocs)
    } catch {}
  }

  const startNewChat = async (threadList = threads) => {
    const newId = uuidv4()
    try {
      await createThread(newId)
      const updated = [{ thread_id: newId, title: 'New Chat', created_at: '', updated_at: '' }, ...threadList]
      setThreads(updated)
      setActiveId(newId)
      setMessages([])
      setDocs([])
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

  const handleFileUploaded = (docRecord) => {
    setDocs(prev => [...prev, docRecord])
    setUploadingFile('')
  }

  const updateThreadTitle = (tid, firstMsg) => {
    const title = firstMsg.slice(0, 50) + (firstMsg.length > 50 ? '...' : '')
    setThreads(prev => prev.map(t => t.thread_id === tid ? { ...t, title } : t))
  }

  const handleSend = useCallback(async (text) => {
    if (!activeId || streaming) return

    // Limit check
    if (!isAdmin && !isApproved && chatCount >= 5) {
      setLimitReached(true)
      return
    }

    const userMsg = { role: 'user', content: text }
    setMessages(prev => {
      if (prev.length === 0) updateThreadTitle(activeId, text)
      return [...prev, userMsg]
    })
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
    setStreaming(true)

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }))
      const streamFn = docs.length > 0
        ? () => streamRagChat(activeId, text, history)
        : () => streamChat(activeId, text)

      let full = ''
      for await (const chunk of streamFn()) {
        full += chunk
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: full }
          return updated
        })
      }
      // Stats refresh after each chat
      refreshStats()
    } catch (err) {
      if (err.status === 403) {
        setLimitReached(true)
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: `⛔ ${err.message}` }
          return updated
        })
      } else {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: `❌ Error: ${err.message}` }
          return updated
        })
      }
    } finally {
      setStreaming(false)
      try { const list = await getThreads(); setThreads(list) } catch {}
    }
  }, [activeId, streaming, docs, messages, isAdmin, isApproved, chatCount, refreshStats])

  const hasMessages = messages.length > 0
  const chatDisabled = streaming || limitReached

  return (
    <div className="flex h-screen w-full overflow-hidden bg-gray-50">
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={(tid) => loadThread(tid)}
        onNew={() => startNewChat()}
        onDeleted={handleDeleted}
        onRenamed={handleRenamed}
        onAdminClick={() => navigate('/admin')}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full">

        {/* Chat limit banner — free users only */}
        {limitReached && (
          <div className="bg-red-50 border-b border-red-200 px-4 py-3 flex items-center gap-3">
            <AlertTriangle size={16} className="text-red-500 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-700">Chat limit reached (5/5)</p>
              <p className="text-xs text-red-500">Contact admin at kashyap040098@gmail.com for unlimited access.</p>
            </div>
          </div>
        )}

        {/* Free user soft warning (not yet reached) */}
        {!limitReached && !isAdmin && !isApproved && chatCount > 0 && chatCount < 5 && (
          <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center gap-2">
            <span className="text-xs text-yellow-700">
              ⚠️ Free plan: <strong>{5 - chatCount} chats remaining</strong> — Contact admin for unlimited access
            </span>
          </div>
        )}

        <DocPanel docs={docs} onDocsChange={setDocs} uploadingFile={uploadingFile} />

        <div className="flex-1 overflow-y-auto">
          {!hasMessages ? (
            <div className="h-full flex flex-col items-center justify-center gap-4 px-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center shadow-lg">
                <Bot size={32} className="text-white" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-gray-800 mb-1">How can I help you today?</h2>
                <p className="text-sm text-gray-500 max-w-sm">
                  Ask anything, or click <strong>+</strong> to upload a PDF or image and ask questions about it.
                </p>
              </div>
              {!limitReached && (
                <div className="flex flex-wrap justify-center gap-2 max-w-lg mt-2">
                  {['📰 Latest tech news', '🧮 Calculate 15% of 2450', '📖 Explain quantum computing', '💡 Give me 5 productivity tips'].map(s => (
                    <button key={s} onClick={() => handleSend(s.slice(3))}
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
                <MessageBubble key={i} role={msg.role} content={msg.content}
                  isStreaming={streaming && i === messages.length - 1 && msg.role === 'assistant'} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="border-t border-gray-100 bg-white">
          <ChatInput
            threadId={activeId}
            disabled={chatDisabled}
            limitReached={limitReached}
            onSend={handleSend}
            onFileUploaded={handleFileUploaded}
          />
        </div>
      </div>
    </div>
  )
}
