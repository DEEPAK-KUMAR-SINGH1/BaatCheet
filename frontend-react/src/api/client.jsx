function getToken() {
  return sessionStorage.getItem('token') || ''
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
  }
}

export const authSignup = (email, password) =>
  post('/auth/signup', { email, password }, false)

export const authSignupVerify = (email, otp) =>
  post('/auth/signup/verify', { email, otp }, false)

export const authLogin = (email, password) =>
  post('/auth/login', { email, password }, false)

export const authLoginVerify = (email, otp) =>
  post('/auth/login/verify', { email, otp }, false)

export const authForgotPassword = (email) =>
  post('/auth/forgot-password', { email }, false)

export const authForgotVerify = (email, otp, new_password) =>
  post('/auth/forgot-password/verify', { email, otp, new_password }, false)

export const getMyStats = () => get('/auth/me/stats')

export const getThreads = () => get('/threads')

export const createThread = (thread_id, workspace_id = null) =>
  post('/threads', { thread_id, title: 'New Chat', workspace_id })

export const renameThread = (thread_id, title) =>
  patch(`/threads/${thread_id}/title`, { title })

export const deleteThread = (thread_id) =>
  del(`/threads/${thread_id}`)

export const getThreadMessages = (thread_id) =>
  get(`/threads/${thread_id}/messages`)

export const editMessage = (thread_id, message_id, content) =>
  patch(`/threads/${thread_id}/messages/${message_id}`, { content })

export const attachThreadWorkspace = (thread_id, workspace_id) =>
  patch(`/threads/${thread_id}/workspace`, { workspace_id })

export const getWorkspaces = () => get('/workspaces')

export const createWorkspace = (name) =>
  post('/workspaces', { name })

export const updateWorkspace = (workspace_id, name, description = '') =>
  patch(`/workspaces/${workspace_id}`, { name, description })

export const deleteWorkspace = (workspace_id) =>
  del(`/workspaces/${workspace_id}`)

export const getWorkspaceDocs = (workspace_id) =>
  get(`/workspaces/${workspace_id}/documents`)

export const getDocs = (thread_id) =>
  get(`/rag/documents/${thread_id}`)

export const deleteDoc = (doc_id) =>
  del(`/rag/documents/${doc_id}`)

export const deleteWorkspaceDoc = (workspace_id, doc_id) =>
  del(`/workspaces/${workspace_id}/documents/${doc_id}`)

export const retryWorkspaceDoc = (workspace_id, doc_id) =>
  post(`/workspaces/${workspace_id}/documents/${doc_id}/retry`, {})

export const getSourceChunk = (doc_id, chunk_index) =>
  get(`/sources/${doc_id}/chunks/${chunk_index}`)

export const searchConversations = (q) =>
  get(`/search?q=${encodeURIComponent(q)}`)

export const adminGetUsers = () => get('/admin/users')

export const adminGetAnalytics = (days = 30) =>
  get(`/admin/analytics?days=${days}`)

export const adminGetThreads = (limit = 50) =>
  get(`/admin/threads?limit=${limit}`)

export const adminDeleteThread = (thread_id) =>
  del(`/admin/threads/${thread_id}`)

export const adminGetDocuments = (limit = 50) =>
  get(`/admin/documents?limit=${limit}`)

export const adminDeleteDocument = (doc_id) =>
  del(`/admin/documents/${doc_id}`)

export const adminApproveUser = (email) =>
  post('/admin/users/approve', { email })

export const adminRevokeUser = (email) =>
  post('/admin/users/revoke', { email })

export const shareThread = (thread_id) =>
  post(`/threads/${thread_id}/share`, {})

export const getThreadShare = (thread_id) =>
  get(`/threads/${thread_id}/share`)

export const revokeThreadShare = (thread_id) =>
  del(`/threads/${thread_id}/share`)

export const getPublicShare = (token) =>
  getPublic(`/public/share/${token}`)

export const getMcpConnections = () =>
  get('/mcp/connections')

export const connectGmail = () =>
  post('/mcp/gmail/connect', {})

export const disconnectGmail = () =>
  del('/mcp/gmail')

// LinkedIn MCP
export const connectLinkedin = () =>
  post('/mcp/linkedin/connect', {})
export const disconnectLinkedin = () =>
  del('/mcp/linkedin')

// Google Drive MCP
export const connectGoogleDrive = () =>
  post('/mcp/google_drive/connect', {})
export const disconnectGoogleDrive = () =>
  del('/mcp/google_drive')

// YouTube MCP
export const connectYoutube = () =>
  post('/mcp/youtube/connect', {})
export const disconnectYoutube = () =>
  del('/mcp/youtube')

// Telegram MCP
export const connectTelegram = () =>
  post('/mcp/telegram/connect', {})
export const disconnectTelegram = () =>
  del('/mcp/telegram')

// Notion MCP
export const connectNotion = () =>
  post('/mcp/notion/connect', {})
export const disconnectNotion = () =>
  del('/mcp/notion')

// Trello MCP
export const connectTrello = () =>
  post('/mcp/trello/connect', {})
export const disconnectTrello = () =>
  del('/mcp/trello')

export const exportThread = async (thread_id, format = 'markdown') => {
  const res = await fetch(`/threads/${thread_id}/export?format=${encodeURIComponent(format)}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!res.ok) throw new Error(await readError(res, 'Export failed'))
  const blob = await res.blob()
  const ext = format === 'pdf' ? 'pdf' : 'md'
  downloadBlob(blob, `chat-${thread_id}.${ext}`)
}

export async function* streamChat(thread_id, message, workspace_id = null, signal) {
  yield* streamEvents('/chat', { thread_id, message, workspace_id }, signal)
}

export async function* regenerateThread(thread_id, workspace_id = null, signal) {
  yield* streamEvents(`/threads/${thread_id}/regenerate`, { thread_id, message: '', workspace_id }, signal)
}

export async function* streamRagChat(thread_id, message, chat_history, signal) {
  yield* streamEvents('/rag/chat', { thread_id, message, chat_history }, signal)
}

export const uploadDoc = async (thread_id, file, onProgress) => {
  const form = new FormData()
  form.append('thread_id', thread_id)
  form.append('file', file)
  return xhrUpload('/rag/upload', form, onProgress)
}

export const uploadWorkspaceDoc = async (workspace_id, thread_id, file, onProgress) => {
  const form = new FormData()
  form.append('thread_id', thread_id)
  form.append('file', file)
  return xhrUpload(`/workspaces/${workspace_id}/documents`, form, onProgress)
}

async function get(url) {
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) throw new Error(await readError(res, `GET ${url} failed`))
  return res.json()
}

async function getPublic(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(await readError(res, `GET ${url} failed`))
  return res.json()
}

async function post(url, body, withAuth = true) {
  const headers = withAuth
    ? authHeaders()
    : { 'Content-Type': 'application/json' }
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  const data = await readJsonSafely(res)
  if (!res.ok) throw toApiError(data, `POST ${url} failed`, res.status)
  return data
}

async function patch(url, body) {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  const data = await readJsonSafely(res)
  if (!res.ok) throw toApiError(data, `PATCH ${url} failed`, res.status)
  return data
}

async function del(url) {
  const res = await fetch(url, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  const data = await readJsonSafely(res)
  if (!res.ok) throw toApiError(data, `DELETE ${url} failed`, res.status)
  return data
}

async function* streamEvents(url, body, signal) {
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
    signal,
  })
  if (res.status === 403) {
    const data = await res.json()
    const err = new Error(data.detail || 'Chat limit reached')
    err.status = 403
    throw err
  }
  if (res.status === 401) {
    const err = new Error('Session expired. Please login again.')
    err.status = 401
    throw err
  }
  if (!res.ok) throw new Error(await readError(res, 'Chat request failed'))
  yield* parseNDJSON(res.body)
}

function xhrUpload(url, form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      let data = {}
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : {}
      } catch {
        data = { detail: xhr.responseText }
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(toApiError(data, 'Upload failed', xhr.status))
    }
    xhr.onerror = () => reject(new Error('Upload failed'))
    xhr.send(form)
  })
}

async function readJsonSafely(res) {
  const text = await res.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

function extractErrorMessage(data, fallback) {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (typeof data.detail === 'string') return data.detail
  if (typeof data.message === 'string') return data.message
  return fallback
}

function toApiError(data, fallback, status) {
  const err = new Error(extractErrorMessage(data, fallback))
  err.status = status
  return err
}

async function readError(res, fallback) {
  const data = await readJsonSafely(res)
  return extractErrorMessage(data, fallback)
}

async function* parseNDJSON(body) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const obj = JSON.parse(line)
        if (obj.done) return
        if (obj.t != null) yield { type: 'token', text: obj.t }
        else if (obj.sources != null) yield { type: 'sources', sources: obj.sources }
        else if (obj.error != null) yield { type: 'error', error: obj.error }
      } catch {}
    }
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
