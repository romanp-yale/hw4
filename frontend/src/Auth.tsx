import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export type User = { id: number; first_name: string | null; last_name: string | null; name: string; email: string }
type AuthContextValue = {
  user: User | null
  loading: boolean
  register: (input: { first_name: string; last_name: string; email: string; password: string }) => Promise<void>
  login: (input: { email: string; password: string }) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function authRequest(path: string, body?: object): Promise<{ user: User }> {
  const response = await fetch(`/api/auth/${path}`, {
    method: body ? 'POST' : 'GET',
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    const detail = result.detail
    throw new Error(typeof detail === 'string' ? detail : 'Please check your details and try again.')
  }
  return response.json()
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    authRequest('me').then(result => setUser(result.user)).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])
  async function register(input: { first_name: string; last_name: string; email: string; password: string }) {
    const result = await authRequest('register', input)
    setUser(result.user)
  }
  async function login(input: { email: string; password: string }) {
    const result = await authRequest('login', input)
    setUser(result.user)
  }
  async function logout() {
    await authRequest('logout', {})
    setUser(null)
  }
  return <AuthContext.Provider value={{ user, loading, register, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider is missing.')
  return context
}

export function LoginPage() {
  const navigate = useNavigate()
  const { login, user } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login({ email, password })
      navigate('/account')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Login failed.')
    } finally {
      setBusy(false)
    }
  }
  if (user) return <AccountPage />
  return <main className="auth-page"><section className="auth-card"><span className="eyebrow">WELCOME BACK</span><h1>Log in</h1><p>Pick up where you left off in Bulldog blue.</p><form onSubmit={submit}>
    <label>Email address<input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
    <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label>
    {error && <div className="form-error" role="alert">{error}</div>}
    <button className="button primary auth-submit" disabled={busy} type="submit">{busy ? 'Logging in…' : 'Log in ↗'}</button>
  </form><p className="auth-switch">New here? <Link to="/create-account">Create an account</Link></p></section></main>
}

export function RegisterPage() {
  const navigate = useNavigate()
  const { register, user } = useAuth()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await register({ first_name: firstName.trim(), last_name: lastName.trim(), email, password })
      navigate('/account')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Account could not be created.')
    } finally {
      setBusy(false)
    }
  }
  if (user) return <AccountPage />
  return <main className="auth-page"><section className="auth-card"><span className="eyebrow">JOIN CAMPUS CUSTOMS</span><h1>Create account</h1><p>Make a space for your next campus find.</p><form onSubmit={submit}>
    <div className="name-row"><label>First name<input autoComplete="given-name" required maxLength={80} value={firstName} onChange={event => setFirstName(event.target.value)} /></label><label>Last name<input autoComplete="family-name" required maxLength={80} value={lastName} onChange={event => setLastName(event.target.value)} /></label></div>
    <label>Email address<input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
    <label>Password<input type="password" autoComplete="new-password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} /><small>Use at least 8 characters.</small></label>
    <label>Confirm password<input type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
    {error && <div className="form-error" role="alert">{error}</div>}
    <button className="button primary auth-submit" disabled={busy} type="submit">{busy ? 'Creating account…' : 'Create account ↗'}</button>
  </form><p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p></section></main>
}

export function AccountPage() {
  const navigate = useNavigate()
  const { user, loading, logout } = useAuth()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function signOut() {
    setBusy(true)
    setError('')
    try {
      await logout()
      navigate('/login')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Logout failed.')
    } finally {
      setBusy(false)
    }
  }
  if (loading) return <main className="auth-page"><p>Checking your session…</p></main>
  if (!user) return <main className="auth-page"><section className="auth-card"><h1>Your account</h1><p>Please log in to view your account.</p><Link to="/login" className="button primary">Log in ↗</Link></section></main>
  return <main className="auth-page"><section className="auth-card"><span className="eyebrow">YOUR CAMPUS CUSTOMS ACCOUNT</span><h1>Hi, {user.first_name || user.name}.</h1><p>You’re logged in as <strong>{user.email}</strong>.</p><div className="account-actions"><Link to="/products" className="button primary">Browse products ↗</Link><button type="button" onClick={signOut} disabled={busy} className="button outline">{busy ? 'Logging out…' : 'Log out'}</button></div>{error && <div className="form-error" role="alert">{error}</div>}</section></main>
}
