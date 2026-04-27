import { useState, useEffect, createContext, useContext } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken]         = useState(null)
  const [email, setEmail]         = useState(null)
  const [isAdmin, setIsAdmin]     = useState(false)
  const [isApproved, setIsApproved] = useState(false)
  const [chatCount, setChatCount] = useState(0)
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    // sessionStorage use karo taaki har tab mein alag user login kar sake
    const savedToken    = sessionStorage.getItem('token')
    const savedEmail    = sessionStorage.getItem('email')
    const savedAdmin    = sessionStorage.getItem('is_admin') === 'true'
    const savedApproved = sessionStorage.getItem('is_approved') === 'true'

    if (!savedToken) { setLoading(false); return }

    fetch('/auth/me/stats', {
      headers: { Authorization: `Bearer ${savedToken}` }
    })
      .then(res => {
        if (res.ok) return res.json()
        sessionStorage.removeItem('token')
        sessionStorage.removeItem('email')
        sessionStorage.removeItem('is_admin')
        sessionStorage.removeItem('is_approved')
        return null
      })
      .then(data => {
        if (data) {
          setToken(savedToken)
          setEmail(savedEmail)
          setIsAdmin(data.is_admin)
          setIsApproved(data.is_approved)
          setChatCount(data.chat_count)
          sessionStorage.setItem('is_admin', data.is_admin)
          sessionStorage.setItem('is_approved', data.is_approved)
        }
      })
      .catch(() => {
        // Backend down — trust sessionStorage
        setToken(savedToken)
        setEmail(savedEmail)
        setIsAdmin(savedAdmin)
        setIsApproved(savedApproved)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = (tok, em, admin = false, approved = false) => {
    sessionStorage.setItem('token', tok)
    sessionStorage.setItem('email', em)
    sessionStorage.setItem('is_admin', admin)
    sessionStorage.setItem('is_approved', approved)
    setToken(tok)
    setEmail(em)
    setIsAdmin(admin)
    setIsApproved(approved)
  }

  const logout = () => {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('email')
    sessionStorage.removeItem('is_admin')
    sessionStorage.removeItem('is_approved')
    setToken(null)
    setEmail(null)
    setIsAdmin(false)
    setIsApproved(false)
    setChatCount(0)
  }

  const refreshStats = () => {
    if (!token) return
    fetch('/auth/me/stats', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setIsAdmin(data.is_admin)
          setIsApproved(data.is_approved)
          setChatCount(data.chat_count)
        }
      })
      .catch(() => {})
  }

  return (
    <AuthContext.Provider value={{
      token, email, isAdmin, isApproved, chatCount,
      login, logout, refreshStats,
      isAuth: !!token, loading
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
