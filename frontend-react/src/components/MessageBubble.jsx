import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Bot, User, Copy, Check } from 'lucide-react'
import { useState } from 'react'

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy}
      className="absolute top-2 right-2 p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white/70 transition">
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  )
}

const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '')
    const code = String(children).replace(/\n$/, '')
    if (!inline && match) {
      return (
        <div className="relative my-3">
          <div className="absolute top-2 left-3 text-xs text-white/50 font-mono">{match[1]}</div>
          <CopyBtn text={code} />
          <SyntaxHighlighter
            style={oneDark}
            language={match[1]}
            PreTag="div"
            customStyle={{ borderRadius: '10px', padding: '2.5rem 1rem 1rem', margin: 0, fontSize: '0.85rem' }}
            {...props}
          >
            {code}
          </SyntaxHighlighter>
        </div>
      )
    }
    return <code className={className} {...props}>{children}</code>
  }
}

export default function MessageBubble({ role, content, isStreaming }) {
  const isUser = role === 'user'

  return (
    <div className={`flex gap-3 mb-5 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center
        ${isUser
          ? 'bg-gradient-to-br from-primary-500 to-purple-600'
          : 'bg-gray-100 border border-gray-200'}`}>
        {isUser
          ? <User size={15} className="text-white" />
          : <Bot size={15} className="text-primary-500" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm
        ${isUser
          ? 'bg-gradient-to-br from-primary-500 to-purple-600 text-white rounded-tr-sm'
          : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-sm'}`}>
        {isUser ? (
          <p className="leading-relaxed">{content}</p>
        ) : (
          <div className={`prose-chat ${isStreaming ? 'stream-cursor' : ''}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
