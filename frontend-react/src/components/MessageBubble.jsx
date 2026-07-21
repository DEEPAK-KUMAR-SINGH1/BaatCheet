import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Bot, User, Copy, Check, RotateCcw, Pencil } from 'lucide-react'
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

function SourceChips({ sources, onSourceClick }) {
  if (!sources?.length) return null
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {sources.map((source, idx) => (
        <button key={`${source.doc_id}-${source.chunk_index}-${idx}`}
          onClick={() => onSourceClick?.(source)}
          className="text-[11px] px-2 py-1 rounded-full bg-primary-50 text-primary-700 border border-primary-100 hover:bg-primary-100 transition">
          {source.label || `S${idx + 1}`} - {source.filename}{source.page ? ` p.${source.page}` : ''}
        </button>
      ))}
    </div>
  )
}

function StreamingText({ content }) {
  return (
    <div className="streaming-text">
      {content || ' '}
      <span className="stream-cursor" aria-hidden="true" />
    </div>
  )
}

export default function MessageBubble({
  role,
  content,
  metadata,
  status,
  isStreaming,
  canEdit,
  canRegenerate,
  onEdit,
  onRegenerate,
  onSourceClick,
}) {
  const isUser = role === 'user'
  const sources = metadata?.sources || []

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
      <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm relative group
        ${isUser
          ? 'bg-gradient-to-br from-primary-500 to-purple-600 text-white rounded-tr-sm'
          : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-sm'}`}>
        {(canEdit || canRegenerate) && !isStreaming && (
          <div className={`absolute -top-3 ${isUser ? 'left-2' : 'right-2'} opacity-0 group-hover:opacity-100 transition flex gap-1`}>
            {canEdit && (
              <button onClick={onEdit} className="p-1.5 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-primary-600 shadow-sm">
                <Pencil size={12} />
              </button>
            )}
            {canRegenerate && (
              <button onClick={onRegenerate} className="p-1.5 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-primary-600 shadow-sm">
                <RotateCcw size={12} />
              </button>
            )}
          </div>
        )}
        {isUser ? (
          <p className="leading-relaxed">{content}</p>
        ) : (
          <>
            {isStreaming ? (
              <StreamingText content={content} />
            ) : (
              <div className="prose-chat">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                  {content}
                </ReactMarkdown>
              </div>
            )}
            {status === 'stopped' && (
              <p className="mt-2 text-[11px] font-semibold text-amber-600">Stopped early</p>
            )}
            <SourceChips sources={sources} onSourceClick={onSourceClick} />
          </>
        )}
      </div>
    </div>
  )
}
