import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from './Auth'
import type { ProductCardData } from './ProductCard'

type ChatResponse = { reply: string; products: ProductCardData[]; search_query: string | null; model: string }
type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
  local?: boolean
  error?: boolean
}

function chatText(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith('**') && part.endsWith('**')
    ? <strong key={index}>{part.slice(2, -2)}</strong>
    : part)
}

export default function Chat({ onResults }: { onResults: (query: string, products: ProductCardData[]) => void }) {
  const { user, loading: authLoading } = useAuth()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([{
    role: 'assistant', text: 'Hi! Tell me what kind of Campus Customs gear you’re looking for. Please don’t share passwords or account details here.', local: true,
  }])
  useEffect(() => {
    if (authLoading) return
    if (!user) {
      setMessages([{ role: 'assistant', text: 'Hi! Tell me what kind of Campus Customs gear you’re looking for. Please don’t share passwords or account details here.', local: true }])
      setHistoryLoading(false)
      return
    }
    const controller = new AbortController()
    setHistoryLoading(true)
    fetch('/api/chat/history', { signal: controller.signal, credentials: 'same-origin' })
      .then(async response => {
        if (!response.ok) throw new Error('Saved chat history could not be loaded.')
        return response.json() as Promise<{ role: 'user' | 'assistant'; content: string }[]>
      })
      .then(turns => setMessages(turns.length ? turns.map(turn => ({ role: turn.role, text: turn.content })) : [{ role: 'assistant', text: `Hi, ${user.first_name || user.name}! What Campus Customs gear can I help you find?`, local: true }]))
      .catch(error => { if (error.name !== 'AbortError') setMessages([{ role: 'assistant', text: 'Saved chat history could not be loaded. You can still send a message.', local: true, error: true }]) })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false) })
    return () => controller.abort()
  }, [authLoading, user?.id])

  const segments = location.pathname.split('/').filter(Boolean)
  const page = segments[0] === 'products' && segments[1]
    ? { kind: 'product', product_id: decodeURIComponent(segments[1]) }
    : { kind: segments[0] === 'products' ? 'products' : segments[0] === 'about' ? 'about' : segments[0] === 'account' ? 'account' : segments.length ? 'other' : 'home' }

  useEffect(() => {
    if (open && messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
  }, [messages, busy, open])

  async function sendMessage(rawMessage: string) {
    const message = rawMessage.trim()
    if (!message || busy || historyLoading || authLoading) return
    const history = messages.filter(item => !item.local).slice(-12).map(item => ({
      role: item.role, content: item.text,
    }))
    setMessages(current => [...current, { role: 'user', text: message }])
    setDraft('')
    setBusy(true)
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ message, history, page }),
        signal: AbortSignal.timeout(60000),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(typeof data.detail === 'string' ? data.detail : `Chat request failed (${response.status}).`)
      }
      const data = await response.json() as ChatResponse
      setMessages(current => [...current, { role: 'assistant', text: data.reply }])
      onResults(data.search_query || message, data.products)
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : 'Unknown error.'
      setMessages(current => [...current, {
        role: 'assistant', text: `Shop assistant unavailable: ${detail}`, local: true, error: true,
      }])
    } finally {
      setBusy(false)
    }
  }

  function send(event: FormEvent) {
    event.preventDefault()
    void sendMessage(draft)
  }

  const starters = page.kind === 'product'
    ? ['What colors does this come in?', 'Do you have this in medium?']
    : ['Show me hoodies', 'What navy styles do you have?', 'Which hoodies are in stock in medium?']
  const showStarters = !busy && !historyLoading && !authLoading

  return <div className="chat-wrap">
    {open && <section className="chat-panel" aria-label="Shop assistant">
      <div className="chat-head"><div><small className="chat-kicker">CAMPUS CUSTOMS / CONCIERGE</small><strong><span className="chat-dot" /> Shop assistant</strong><small>Answers from the local catalogue</small></div><button onClick={() => setOpen(false)} aria-label="Close chat">×</button></div>
      <div className="chat-messages" ref={messagesRef} aria-live="polite">{historyLoading && <div className="message assistant">Loading your saved chat…</div>}{messages.map((item, index) => <div className={`chat-entry ${item.role}`} key={index}>
        <div className={`message ${item.role}${item.error ? ' error' : ''}`}>{chatText(item.text)}</div>
      </div>)}{busy && <div className="message assistant chat-thinking"><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span> Looking through the catalogue…</div>}</div>
      {showStarters && <div className="chat-starters" aria-label="Suggested questions"><span>TRY A QUESTION</span>{starters.map(prompt => <button key={prompt} type="button" onClick={() => void sendMessage(prompt)}>{prompt} <span aria-hidden="true">↗</span></button>)}</div>}
      <form onSubmit={send} className="chat-form"><input value={draft} onChange={event => setDraft(event.target.value)} placeholder="Ask about styles, colors, or stock…" aria-label="Chat message" maxLength={2000} disabled={busy || historyLoading || authLoading} /><button type="submit" aria-label="Send message" disabled={busy || historyLoading || authLoading || !draft.trim()}>↗</button></form>
    </section>}
    <button className="chat-toggle" onClick={() => setOpen(!open)} aria-label={open ? 'Close chat' : 'Open shop assistant'}>{open ? '×' : '✦'}<span>{open ? 'Close chat' : 'Ask about your next favorite'}</span></button>
  </div>
}
