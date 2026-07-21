import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth.jsx'
import AuthPage  from './pages/AuthPage'
import ChatPage  from './pages/ChatPage'
import AdminPage from './pages/AdminPage'
import SharePage from './pages/SharePage'

function LoadingScreen() {
  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mb-4 shadow-lg">
        <span className="text-2xl">🤖</span>
      </div>
      <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-gray-400 mt-3">Loading...</p>
    </div>
  )
}

function PrivateRoute({ children }) {
  const { isAuth, loading } = useAuth()
  if (loading) return <LoadingScreen />
  return isAuth ? children : <Navigate to="/auth" replace />
}

function AdminRoute({ children }) {
  const { isAuth, isAdmin, loading } = useAuth()
  if (loading) return <LoadingScreen />
  if (!isAuth)  return <Navigate to="/auth" replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return children
}

function PublicRoute({ children }) {
  const { isAuth, loading } = useAuth()
  if (loading) return <LoadingScreen />
  return !isAuth ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/share/:token" element={<SharePage />} />
        <Route path="/auth" element={<PublicRoute><AuthPage /></PublicRoute>} />
        <Route path="/"     element={<PrivateRoute><ChatPage /></PrivateRoute>} />
        <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
