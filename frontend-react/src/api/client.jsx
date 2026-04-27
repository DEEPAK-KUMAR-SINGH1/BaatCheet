// Auth token helper — sessionStorage use karo taaki multiple users alag tabs mein login kar sakein
function getToken() {
  return sessionStorage.getItem('token') || ''
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`
  }
}

// ─── AUTH ───────────────────────────────

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

// ─── THREADS ────────────────────────────

export const getThreads = () => get('/threads')

export const createThread = (thread_id) =>
  post('/threads', { thread_id, title: 'New Chat' })

export const renameThread = (thread_id, title) =>
  patch(`/threads/${thread_id}/title`, { title })

export const deleteThread = (thread_id) =>
  del(`/threads/${thread_id}`)

export const getThreadMessages = (thread_id) =>
  get(`/threads/${thread_id}/messages`)

// ─── REGULAR CHAT (NDJSON stream) ───────

export async function* streamChat(thread_id, message) {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ thread_id, message })
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
  if (!res.ok) throw new Error('Chat request failed')
  yield* parseNDJSON(res.body)
}

// ─── RAG ────────────────────────────────

export const getDocs = (thread_id) =>
  get(`/rag/documents/${thread_id}`)

export const deleteDoc = (doc_id) =>
  del(`/rag/documents/${doc_id}`)

export const uploadDoc = async (thread_id, file) => {
  const form = new FormData()
  form.append('thread_id', thread_id)
  form.append('file', file)
  const res = await fetch('/rag/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${getToken()}` },
    body: form
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Upload failed')
  return data
}

export async function* streamRagChat(thread_id, message, chat_history) {
  const res = await fetch('/rag/chat', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ thread_id, message, chat_history })
  })
  if (res.status === 403) {
    const data = await res.json()
    const err = new Error(data.detail || 'Chat limit reached')
    err.status = 403
    throw err
  }
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'RAG chat failed')
  }
  yield* parseNDJSON(res.body)
}

// ─── ADMIN ──────────────────────────────

export const adminGetUsers = () => get('/admin/users')

export const adminApproveUser = (email) =>
  post('/admin/users/approve', { email })

export const adminRevokeUser = (email) =>
  post('/admin/users/revoke', { email })

// ─── HELPERS ────────────────────────────

async function get(url) {
  const res = await fetch(url, { headers: authHeaders() })
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
    body: JSON.stringify(body)
  })
  const data = await readJsonSafely(res)
  if (!res.ok) throw new Error(extractErrorMessage(data, `POST ${url} failed`))
  return data
}

async function patch(url, body) {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(await readError(res, `PATCH ${url} failed`))
  return res.json()
}

async function del(url) {
  const res = await fetch(url, {
    method: 'DELETE',
    headers: authHeaders()
  })
  if (!res.ok) throw new Error(await readError(res, `DELETE ${url} failed`))
  return res.json()
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

async function readError(res, fallback) {
  const data = await readJsonSafely(res)
  return extractErrorMessage(data, fallback)
}

async function* parseNDJSON(body) {
  const reader  = body.getReader()
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
        if (obj.t != null) yield obj.t
      } catch {}
    }
  }
}
