import { useState } from 'react'
import { useAuth } from '../hooks/useAuth.jsx'
import { authSignup, authSignupVerify, authLogin, authForgotPassword, authForgotVerify } from '../api/client.jsx'
import { Mail, Lock, Eye, EyeOff, Bot, ArrowRight, RefreshCw } from 'lucide-react'

function Input({ icon: Icon, type = 'text', placeholder, value, onChange, rightIcon, onRightClick }) {
  // readOnly trick: Chrome autofill sirf editable fields mein karta hai.
  // onFocus pe readOnly hatao — user type kar sakta hai, browser fill nahi kar sakta.
  const [ro, setRo] = useState(true)
  return (
    <div className="relative flex items-center">
      {/* Fake hidden inputs — Chrome inhe password manager ke liye use karta hai, asli fields nahi */}
      {type === 'password' && (
        <>
          <input type="text" style={{ display: 'none' }} />
          <input type="password" style={{ display: 'none' }} />
        </>
      )}
      <Icon size={17} className="absolute left-3.5 text-gray-400 pointer-events-none" />
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        readOnly={ro}
        onFocus={() => setRo(false)}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        data-form-type="other"
        data-lpignore="true"
        className="w-full pl-10 pr-10 py-3 rounded-xl border border-gray-200
                   focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100
                   bg-white text-sm transition"
      />
      {rightIcon && (
        <button type="button" onClick={onRightClick}
          className="absolute right-3 text-gray-400 hover:text-gray-600">
          {rightIcon}
        </button>
      )}
    </div>
  )
}

function Btn({ children, onClick, loading, type = 'button', variant = 'primary' }) {
  const base = "w-full py-3 rounded-xl font-semibold text-sm transition flex items-center justify-center gap-2"
  const styles = variant === 'primary'
    ? "bg-gradient-to-r from-primary-500 to-purple-600 text-white hover:opacity-90"
    : "border border-primary-500 text-primary-500 hover:bg-primary-50"
  return (
    <button type={type} onClick={onClick} disabled={loading}
      className={`${base} ${styles} ${loading ? 'opacity-60 cursor-not-allowed' : ''}`}>
      {loading ? <RefreshCw size={16} className="animate-spin" /> : children}
    </button>
  )
}

function Alert({ msg, type }) {
  if (!msg) return null
  const cls = type === 'error'
    ? 'bg-red-50 border border-red-200 text-red-700'
    : 'bg-green-50 border border-green-200 text-green-700'
  return <div className={`${cls} text-sm rounded-xl px-4 py-3 text-center`}>{msg}</div>
}

function OTPStep({ email, purpose, onBack }) {
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()

  const verify = async () => {
    if (otp.length !== 6) return setError('Enter 6-digit OTP')
    setLoading(true); setError('')
    try {
      const res = await authSignupVerify(email, otp)
      // is_admin + is_approved bhi save karo
      login(res.token, res.email, res.is_admin || false, res.is_approved || false)
    } catch (e) {
      setError(e.message)
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-5">
      <div className="text-center">
        <div className="w-14 h-14 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-3">
          <Mail size={24} className="text-primary-500" />
        </div>
        <p className="text-sm text-gray-500">OTP sent to</p>
        <p className="font-semibold text-gray-800">{email}</p>
      </div>
      <Alert msg={error} type="error" />
      <div>
        <label className="text-sm font-medium text-gray-600 mb-1.5 block">Enter 6-digit OTP</label>
        <input
          type="text" maxLength={6} value={otp}
          onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
          placeholder="○ ○ ○ ○ ○ ○"
          className="otp-input w-full py-3 px-4 border border-gray-200 rounded-xl
                     focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
        />
        <p className="text-xs text-gray-400 mt-2 text-center">Valid for 10 minutes</p>
      </div>
      <Btn onClick={verify} loading={loading}>Verify <ArrowRight size={16} /></Btn>
      <Btn variant="secondary" onClick={onBack}>← Back</Btn>
    </div>
  )
}

function LoginForm({ onSwitch }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()

  const submit = async () => {
    if (!email || !password) return setError('Fill in all fields')
    setLoading(true); setError('')
    try {
      const res = await authLogin(email, password)
      login(res.token, res.email, res.is_admin || false, res.is_approved || false)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <Alert msg={error} type="error" />
      <Input icon={Mail} placeholder="Email address" value={email} onChange={setEmail} />
      <Input icon={Lock} type={showPw ? 'text' : 'password'} placeholder="Password"
        value={password} onChange={setPassword}
        rightIcon={showPw ? <EyeOff size={16} /> : <Eye size={16} />}
        onRightClick={() => setShowPw(p => !p)} />
      <div className="flex justify-end">
        <button onClick={() => onSwitch('forgot')} className="text-xs text-primary-500 hover:underline font-medium">
          Forgot password?
        </button>
      </div>
      <Btn onClick={submit} loading={loading}>Login <ArrowRight size={16} /></Btn>
      <p className="text-center text-sm text-gray-500">
        No account?{' '}
        <button onClick={() => onSwitch('signup')} className="text-primary-500 font-semibold hover:underline">Sign up</button>
      </p>
    </div>
  )
}

function SignupForm({ onSwitch }) {
  const [step, setStep] = useState('form')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!email || !password) return setError('Fill in all fields')
    if (password !== confirm) return setError('Passwords do not match')
    if (password.length < 6) return setError('Password must be at least 6 characters')
    setLoading(true); setError('')
    try {
      await authSignup(email, password)
      setStep('otp')
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  if (step === 'otp') return <OTPStep email={email} purpose="signup" onBack={() => setStep('form')} />

  return (
    <div className="space-y-4">
      <Alert msg={error} type="error" />
      <Input icon={Mail} placeholder="Email address" value={email} onChange={setEmail} />
      <Input icon={Lock} type={showPw ? 'text' : 'password'} placeholder="Password (min 6 chars)"
        value={password} onChange={setPassword}
        rightIcon={showPw ? <EyeOff size={16} /> : <Eye size={16} />}
        onRightClick={() => setShowPw(p => !p)} />
      <Input icon={Lock} type="password" placeholder="Confirm password" value={confirm} onChange={setConfirm} />
      <Btn onClick={submit} loading={loading}>Create Account <ArrowRight size={16} /></Btn>
      <p className="text-center text-sm text-gray-500">
        Already have an account?{' '}
        <button onClick={() => onSwitch('login')} className="text-primary-500 font-semibold hover:underline">Login</button>
      </p>
    </div>
  )
}

function ForgotForm({ onSwitch }) {
  const [step, setStep] = useState('email')
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const sendOtp = async () => {
    if (!email) return setError('Enter your email')
    setLoading(true); setError('')
    try { await authForgotPassword(email); setStep('reset') }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const reset = async () => {
    if (!otp || !newPw) return setError('Fill in all fields')
    if (newPw !== confirmPw) return setError('Passwords do not match')
    if (newPw.length < 6) return setError('Min 6 characters')
    setLoading(true); setError('')
    try {
      await authForgotVerify(email, otp, newPw)
      setSuccess('Password reset! Please login.')
      setTimeout(() => onSwitch('login'), 1500)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <Alert msg={error} type="error" />
      <Alert msg={success} type="success" />
      {step === 'email' ? (
        <>
          <p className="text-sm text-gray-500 text-center">Enter your registered email and we'll send an OTP.</p>
          <Input icon={Mail} placeholder="Registered email" value={email} onChange={setEmail} />
          <Btn onClick={sendOtp} loading={loading}>Send Reset OTP <ArrowRight size={16} /></Btn>
        </>
      ) : (
        <>
          <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-xl px-4 py-3 text-center">
            OTP sent to <strong>{email}</strong>
          </div>
          <input type="text" maxLength={6} value={otp}
            onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
            placeholder="○ ○ ○ ○ ○ ○"
            className="otp-input w-full py-3 px-4 border border-gray-200 rounded-xl focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
          />
          <Input icon={Lock} type="password" placeholder="New password" value={newPw} onChange={setNewPw} />
          <Input icon={Lock} type="password" placeholder="Confirm new password" value={confirmPw} onChange={setConfirmPw} />
          <Btn onClick={reset} loading={loading}>Reset Password <ArrowRight size={16} /></Btn>
          <Btn variant="secondary" onClick={() => setStep('email')}>← Back</Btn>
        </>
      )}
      <p className="text-center text-sm text-gray-500">
        Remember it?{' '}
        <button onClick={() => onSwitch('login')} className="text-primary-500 font-semibold hover:underline">Login</button>
      </p>
    </div>
  )
}

const TITLES = {
  login:  { title: 'Welcome Back',   sub: 'Login to your AI Assistant' },
  signup: { title: 'Create Account', sub: 'Start using AI Assistant today' },
  forgot: { title: 'Reset Password', sub: "We'll send an OTP to your email" },
}

export default function AuthPage() {
  const [view, setView] = useState('login')
  const { title, sub } = TITLES[view]

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-purple-50 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-3xl shadow-xl shadow-primary-100/40 overflow-hidden">
          <div className="bg-gradient-to-r from-primary-500 to-purple-600 px-8 py-8 text-center">
            <div className="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Bot size={32} className="text-white" />
            </div>
            <h1 className="text-white text-2xl font-bold">{title}</h1>
            <p className="text-white/75 text-sm mt-1">{sub}</p>
          </div>
          <div className="px-8 py-8">
            {view === 'login'  && <LoginForm  onSwitch={setView} />}
            {view === 'signup' && <SignupForm onSwitch={setView} />}
            {view === 'forgot' && <ForgotForm onSwitch={setView} />}
          </div>
        </div>
        <p className="text-center text-xs text-gray-400 mt-6">© 2025 AI Assistant · Powered by Mistral + LangGraph</p>
      </div>
    </div>
  )
}
