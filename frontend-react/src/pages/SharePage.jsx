import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, User } from 'lucide-react'
import { getPublicShare } from '../api/client.jsx'

export default function SharePage() {
  const { token } = useParams()
  const [share, setShare] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getPublicShare(token)
      .then(setShare)
      .catch(err => setError(err.message))
  }, [token])

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="bg-white border border-red-100 rounded-3xl px-8 py-6 text-center shadow-sm">
          <h1 className="font-bold text-gray-800 mb-2">Share link unavailable</h1>
          <p className="text-sm text-red-500">{error}</p>
        </div>
      </div>
    )
  }

  if (!share) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 px-6 py-5">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide">Read-only shared chat</p>
          <h1 className="text-xl font-bold text-gray-800 mt-1">{share.title}</h1>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6">
        {share.messages.map((msg, idx) => {
          const isUser = msg.role === 'user'
          return (
            <div key={idx} className={`flex gap-3 mb-5 ${isUser ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center
                ${isUser ? 'bg-primary-500' : 'bg-white border border-gray-200'}`}>
                {isUser ? <User size={15} className="text-white" /> : <Bot size={15} className="text-primary-500" />}
              </div>
              <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm
                ${isUser ? 'bg-primary-500 text-white rounded-tr-sm' : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-sm'}`}>
                {isUser ? (
                  <p className="leading-relaxed">{msg.content}</p>
                ) : (
                  <div className="prose-chat">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </main>
    </div>
  )
}
