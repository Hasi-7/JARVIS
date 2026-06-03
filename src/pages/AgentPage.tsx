import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api, streamAgentMessage } from '@/lib/api';
import type { ConversationSummary } from '@/lib/api';
import { AGENT_MODES, AGENT_STATES } from '@/data/mock';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';

// ── types ─────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id?:         string;
  role:        'user' | 'assistant';
  content:     string;
  timestamp:   string;
  durationMs?: number;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function isoToHHMM(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('en', {
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch { return ''; }
}

function nowHHMM(): string {
  return isoToHHMM(new Date().toISOString());
}

function isoToDateLabel(iso: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const diffH = (Date.now() - d.getTime()) / 3_600_000;
    if (diffH < 24) return isoToHHMM(iso);
    if (diffH < 48) return 'Yesterday';
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

// ── main component ────────────────────────────────────────────────────────────

export function AgentPage() {
  const agentState       = useAppStore((s) => s.agentState);
  const setAgentState    = useAppStore((s) => s.setAgentState);
  const agentMode        = useAppStore((s) => s.agentMode);
  const setAgentMode     = useAppStore((s) => s.setAgentMode);
  const agentStatus      = useAppStore((s) => s.agentStatus);
  const checkAgentStatus = useAppStore((s) => s.checkAgentStatus);
  const backendConfig    = useAppStore((s) => s.backendConfig);
  const agentPrefill     = useAppStore((s) => s.agentPrefill);
  const setAgentPrefill  = useAppStore((s) => s.setAgentPrefill);

  const meta = AGENT_STATES[agentState];

  // ── conversation state ────────────────────────────────────────────────────
  const [convs,         setConvs]         = useState<ConversationSummary[]>([]);
  const [convId,        setConvId]        = useState<string | null>(null);
  const [convTitle,     setConvTitle]     = useState<string>('');
  const [loadingConvs,  setLoadingConvs]  = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // ── chat state ─────────────────────────────────────────────────────────────
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [draft,        setDraft]        = useState('');
  const [error,        setError]        = useState<string | null>(null);
  // null = idle; '' = waiting for first token; non-empty = streaming
  const [streamingMsg, setStreamingMsg] = useState<string | null>(null);
  // Context window metadata from the last meta event
  const [contextInfo,  setContextInfo]  = useState<{ window: number; used: number } | null>(null);

  const isGenerating = streamingMsg !== null;

  // Accumulated streaming content — avoids closure-over-state issues
  const streamContentRef  = useRef('');
  // Whether first token has arrived in the current stream
  const firstTokenRef     = useRef(true);
  // Resolved conversation id from meta event (may differ from convId if newly created)
  const resolvedConvIdRef = useRef<string | null>(null);

  const bottomRef   = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const available = agentStatus?.available ?? false;

  // ── load conversation list ─────────────────────────────────────────────────
  const loadConvList = useCallback(async () => {
    setLoadingConvs(true);
    try {
      const res = await api.listConversations();
      setConvs(res.conversations);
      return res.conversations;
    } catch {
      return [];
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  // ── load a specific conversation's messages ────────────────────────────────
  const loadConv = useCallback(async (id: string) => {
    try {
      const detail = await api.getConversation(id);
      const msgs: ChatMessage[] = detail.messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({
          id:         m.id,
          role:       m.role as 'user' | 'assistant',
          content:    m.content,
          timestamp:  isoToHHMM(m.createdAt),
          durationMs: m.durationMs ?? undefined,
        }));
      setMessages(msgs);
      setConvId(id);
      setConvTitle(detail.title);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation.');
    }
  }, []);

  // ── on mount ───────────────────────────────────────────────────────────────
  useEffect(() => {
    checkAgentStatus();
    loadConvList().then((list) => {
      if (list.length > 0) loadConv(list[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── prefill from Dashboard "Ask" input ────────────────────────────────────
  useEffect(() => {
    if (agentPrefill) {
      setDraft(agentPrefill);
      setAgentPrefill('');
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [agentPrefill, setAgentPrefill]);

  // ── scroll to bottom as messages or stream changes ────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [messages, streamingMsg]);

  // ── send (streaming) ───────────────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = draft.trim();
    if (!text || isGenerating) return;

    setDraft('');
    setError(null);
    streamContentRef.current  = '';
    firstTokenRef.current     = true;
    resolvedConvIdRef.current = convId;

    // Optimistically append user message
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, timestamp: nowHHMM() },
    ]);

    // '' = waiting for first token (shows thinking indicator)
    setStreamingMsg('');
    setAgentState('thinking');

    await streamAgentMessage(
      {
        message:        text,
        mode:           agentMode.id,
        conversationId: convId,
        context: {
          screen:    'Local Agent',
          vaultPath: backendConfig?.vaultPath ?? null,
        },
      },
      {
        onMeta: (m) => {
          resolvedConvIdRef.current = m.conversationId;
          if (!convId) setConvId(m.conversationId);
          if (m.contextWindowMessages !== undefined) {
            setContextInfo({
              window: m.contextWindowMessages,
              used:   m.contextMessagesUsed ?? 0,
            });
          }
        },

        onToken: (tokenText) => {
          if (firstTokenRef.current) {
            firstTokenRef.current = false;
            setAgentState('speaking');
          }
          streamContentRef.current += tokenText;
          setStreamingMsg(streamContentRef.current);
        },

        onDone: async (done) => {
          const full   = streamContentRef.current;
          const ts     = nowHHMM();
          const cid    = resolvedConvIdRef.current;

          // Commit streaming content to messages
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: full, timestamp: ts, durationMs: done.durationMs },
          ]);
          setStreamingMsg(null);
          setAgentState('speaking');
          setTimeout(() => setAgentState('idle'), 3000);

          // Refresh conversation list in background
          try {
            const updated = await api.listConversations();
            setConvs(updated.conversations);
            if (cid) {
              setConvId(cid);
              const found = updated.conversations.find((c) => c.id === cid);
              if (found) setConvTitle(found.title);
            }
          } catch { /* non-fatal */ }
        },

        onError: (err) => {
          setStreamingMsg(null);
          setError(err.message);
          setAgentState('blocked');
          setTimeout(() => setAgentState('idle'), 2000);
        },
      },
    );
  }, [draft, isGenerating, agentMode, convId, backendConfig, setAgentState]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── new conversation ───────────────────────────────────────────────────────
  const handleNewConv = () => {
    setConvId(null);
    setConvTitle('');
    setMessages([]);
    setError(null);
    setStreamingMsg(null);
    setConfirmDelete(null);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  // ── select conversation ────────────────────────────────────────────────────
  const handleSelectConv = async (id: string) => {
    if (id === convId) return;
    setConfirmDelete(null);
    await loadConv(id);
  };

  // ── delete conversation ────────────────────────────────────────────────────
  const handleDeleteConv = async (id: string) => {
    try {
      await api.deleteConversation(id);
      setConfirmDelete(null);
      if (convId === id) {
        setConvId(null);
        setConvTitle('');
        setMessages([]);
      }
      const updated = await api.listConversations();
      setConvs(updated.conversations);
      if (convId === id && updated.conversations.length > 0) {
        await loadConv(updated.conversations[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    }
  };

  // ── derived ────────────────────────────────────────────────────────────────
  const stateColor =
    meta?.tone === 'live'   ? 'var(--live)'   :
    meta?.tone === 'amber'  ? 'var(--amber)'  :
    meta?.tone === 'red'    ? 'var(--red)'    :
    meta?.tone === 'violet' ? 'var(--violet)' :
    meta?.tone === 'green'  ? 'var(--green)'  :
    'var(--grey)';

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', gap: 'var(--s4)', height: '100%', maxWidth: 1200, margin: '0 auto' }}>

      {/* ── left rail ── */}
      <div style={{ width: 220, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 'var(--s4)', overflowY: 'auto' }}>

        {/* conversations list */}
        <div className="panel panel-pad">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--s3)' }}>
            <span className="eyebrow">Conversations</span>
            <button
              className="btn btn-sm btn-ghost"
              style={{ padding: '2px 7px', fontSize: 11 }}
              title="New conversation"
              onClick={handleNewConv}
            >
              <Icon name="plus" size={12} />New
            </button>
          </div>

          {loadingConvs && convs.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>Loading…</div>
          )}

          {!loadingConvs && convs.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--txt-3)', lineHeight: 1.45 }}>
              No conversations yet. Send a message to create one.
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 260, overflowY: 'auto' }}>
            {convs.map((c) => {
              const isActive     = c.id === convId;
              const isConfirming = confirmDelete === c.id;
              return (
                <div
                  key={c.id}
                  style={{
                    borderRadius: 'var(--r2)',
                    background:   isActive ? 'var(--live-bg)' : undefined,
                    border:       `1px solid ${isActive ? 'var(--live-line)' : 'transparent'}`,
                  }}
                >
                  {isConfirming ? (
                    <div style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ fontSize: 10.5, color: 'var(--red)', flex: 1 }}>Delete?</span>
                      <button className="btn btn-sm btn-ghost" style={{ padding: '1px 6px', fontSize: 10.5, color: 'var(--red)' }}
                        onClick={() => handleDeleteConv(c.id)}>Yes</button>
                      <button className="btn btn-sm btn-ghost" style={{ padding: '1px 6px', fontSize: 10.5 }}
                        onClick={() => setConfirmDelete(null)}>No</button>
                    </div>
                  ) : (
                    <div
                      style={{ padding: '6px 8px', display: 'flex', alignItems: 'flex-start', gap: 4, cursor: 'pointer' }}
                      onClick={() => handleSelectConv(c.id)}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 12, fontWeight: isActive ? 600 : 400,
                          color: isActive ? 'var(--live)' : 'var(--txt-0)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {c.title}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 1, display: 'flex', gap: 5 }}>
                          <span>{isoToDateLabel(c.updatedAt)}</span>
                          {c.messageCount > 0 && (
                            <span>{c.messageCount} msg{c.messageCount === 1 ? '' : 's'}</span>
                          )}
                        </div>
                      </div>
                      <button
                        className="btn btn-sm btn-ghost"
                        style={{ padding: '1px 4px', opacity: 0.5, flexShrink: 0, marginTop: 1 }}
                        title="Delete conversation"
                        onClick={(e) => { e.stopPropagation(); setConfirmDelete(c.id); }}
                      >
                        <Icon name="x" size={11} />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* mode selector */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Mode</div>
          {AGENT_MODES.map((m) => {
            const active = m.id === agentMode.id;
            return (
              <button
                key={m.id}
                onClick={() => setAgentMode(m)}
                style={{
                  width: '100%', display: 'flex', flexDirection: 'column', gap: 2,
                  alignItems: 'flex-start', padding: '7px 8px', marginBottom: 2,
                  borderRadius: 'var(--r2)',
                  border: `1px solid ${active ? 'var(--live-line)' : 'transparent'}`,
                  background: active ? 'var(--live-bg)' : 'transparent',
                  cursor: 'pointer', textAlign: 'left',
                  transition: 'background var(--fast) var(--ease)',
                }}
              >
                <span style={{ fontSize: 12, fontWeight: active ? 600 : 500, color: active ? 'var(--live)' : 'var(--txt-0)' }}>
                  {m.label}
                </span>
                <span style={{ fontSize: 10, color: 'var(--txt-2)', lineHeight: 1.3 }}>{m.desc}</span>
              </button>
            );
          })}
        </div>

        {/* local model status */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Local model</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <StatusDot tone={available ? 'green' : 'grey'} pulse={available} />
              <span style={{ fontSize: 12, fontWeight: 500, color: available ? 'var(--green)' : 'var(--txt-3)' }}>
                {agentStatus === null ? 'Checking…' : available ? 'Ready' : 'Unavailable'}
              </span>
            </div>
            {agentStatus && (
              <>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--txt-1)' }}>
                  {agentStatus.model || '—'}
                </div>
                {!available && (
                  <div style={{ fontSize: 10, color: 'var(--amber)', lineHeight: 1.4 }}>
                    {agentStatus.message}
                  </div>
                )}
              </>
            )}
            <button className="btn btn-sm btn-ghost" onClick={checkAgentStatus} style={{ fontSize: 11 }}>
              <Icon name="sync" size={11} />Refresh
            </button>
          </div>
        </div>

        {/* safety notice */}
        <div style={{
          padding: 'var(--s3) var(--s4)', borderRadius: 'var(--r2)',
          background: 'var(--surface-2)', border: '1px solid var(--line)',
          display: 'flex', gap: 6, alignItems: 'flex-start',
        }}>
          <Icon name="shield" size={12} style={{ color: 'var(--amber)', marginTop: 1, flexShrink: 0 }} />
          <span style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
            Uses recent messages from this conversation only.{' '}
            No vault, browser, tools, or long-term memory.
          </span>
        </div>

      </div>

      {/* ── center — cockpit ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--s4)', minWidth: 0 }}>

        {/* cockpit head */}
        <div className="panel panel-pad" style={{ display: 'flex', alignItems: 'center', gap: 'var(--s4)' }}>
          <AgentSphere state={agentState} size={64} variant="orb" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s3)', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Local Agent</span>
              {convTitle && (
                <span style={{ fontSize: 11, color: 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 240 }}>
                  · {convTitle}
                </span>
              )}
              <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--txt-2)', marginTop: 3 }}>
              <span style={{ color: stateColor, fontWeight: 500 }}>{meta?.label}</span>
              {' · '}{meta?.blurb}
              {isGenerating && streamingMsg === '' && (
                <span style={{ color: 'var(--live)', marginLeft: 8 }}>Waiting for model…</span>
              )}
              {isGenerating && streamingMsg !== '' && (
                <span style={{ color: 'var(--live)', marginLeft: 8 }}>Streaming…</span>
              )}
            </div>
          </div>
          {agentStatus && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--txt-3)', flexShrink: 0 }}>
              <StatusDot tone={available ? 'green' : 'grey'} />
              <span className="mono">{agentStatus.model || 'no model'}</span>
            </div>
          )}
        </div>

        {/* conversation panel */}
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>

          {/* scroll area */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--s4) var(--s5)' }}>

            {/* empty state */}
            {messages.length === 0 && !isGenerating && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', minHeight: 160, gap: 'var(--s3)',
                color: 'var(--txt-3)', textAlign: 'center', padding: 'var(--s5)',
              }}>
                <AgentSphere state="idle" size={40} variant="minimal" />
                <div>
                  <div style={{ fontSize: 13, marginBottom: 4, color: 'var(--txt-2)' }}>
                    {convId ? 'Start this conversation' : 'Start a local conversation'}
                  </div>
                  <div style={{ fontSize: 11.5, lineHeight: 1.55 }}>
                    {available
                      ? 'Tools disabled. Responses stream progressively and are saved to local conversation history.'
                      : 'Start Ollama and set BRAIN_UI_LOCAL_MODEL to begin chatting.'}
                  </div>
                </div>
              </div>
            )}

            {/* persisted messages */}
            {messages.map((msg, i) => (
              <div
                key={msg.id ?? i}
                style={{
                  marginBottom: 'var(--s4)',
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  gap: 10, alignItems: 'flex-start',
                }}
              >
                {msg.role === 'assistant' && (
                  <div style={{ flexShrink: 0, marginTop: 2 }}>
                    <AgentSphere state="idle" size={28} variant="minimal" />
                  </div>
                )}
                <div style={{ maxWidth: '76%' }}>
                  <div style={{
                    background: msg.role === 'user' ? 'var(--live-bg)' : 'var(--surface-2)',
                    border: `1px solid ${msg.role === 'user' ? 'var(--live-line)' : 'var(--line)'}`,
                    borderRadius: 'var(--r3)', padding: '10px 14px',
                    fontSize: 13, lineHeight: 1.55, color: 'var(--txt-0)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                  <div style={{
                    fontSize: 10, color: 'var(--txt-3)', marginTop: 3,
                    display: 'flex', gap: 8,
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  }}>
                    <span>{msg.timestamp}</span>
                    {msg.durationMs !== undefined && (
                      <span className="mono">{msg.durationMs.toFixed(0)}ms</span>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* live streaming bubble */}
            {isGenerating && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 'var(--s4)' }}>
                <div style={{ flexShrink: 0, marginTop: 2 }}>
                  <AgentSphere
                    state={streamingMsg === '' ? 'thinking' : 'speaking'}
                    size={28}
                    variant="minimal"
                  />
                </div>
                <div style={{ maxWidth: '76%' }}>
                  <div style={{
                    background: 'var(--surface-2)', border: '1px solid var(--line)',
                    borderRadius: 'var(--r3)', padding: '10px 14px',
                    fontSize: 13, lineHeight: 1.55, color: 'var(--txt-0)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {streamingMsg === '' ? (
                      <span style={{ color: 'var(--txt-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        Thinking
                        <span className="mono" style={{ letterSpacing: '0.1em', fontSize: 11 }}>···</span>
                      </span>
                    ) : (
                      <>
                        {streamingMsg}
                        <span style={{ display: 'inline-block', width: 2, height: '0.9em', background: 'var(--live)', marginLeft: 2, verticalAlign: 'text-bottom', animation: 'blink 0.9s step-end infinite' }} />
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* error strip */}
          {error && (
            <div style={{
              padding: '8px var(--s5)', display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--red-bg)', borderTop: '1px solid var(--red-line)', fontSize: 12,
            }}>
              <StatusDot tone="red" />
              <span style={{ flex: 1, color: 'var(--txt-1)' }}>{error}</span>
              <button className="btn btn-sm btn-ghost" onClick={() => setError(null)} style={{ padding: '2px 8px' }}>
                Dismiss
              </button>
            </div>
          )}

          {/* composer */}
          <div style={{
            padding: 'var(--s3) var(--s4)', borderTop: '1px solid var(--line-soft)',
            display: 'flex', gap: 'var(--s2)', alignItems: 'flex-end',
          }}>
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isGenerating
                  ? 'Waiting for response…'
                  : available
                    ? 'Send a message… (Enter · Shift+Enter for newline)'
                    : 'Local model unavailable — start Ollama to chat'
              }
              disabled={isGenerating || !available}
              rows={2}
              style={{
                flex: 1,
                background: 'var(--surface-2)',
                border: `1px solid ${isGenerating ? 'var(--live-line)' : 'var(--line)'}`,
                borderRadius: 'var(--r2)',
                padding: '9px 12px', fontSize: 13,
                color: 'var(--txt-0)', fontFamily: 'var(--font-ui)',
                outline: 'none', resize: 'none',
                minHeight: 54, maxHeight: 160,
                opacity: (!available || isGenerating) ? 0.5 : 1,
                transition: 'border-color var(--fast) var(--ease), opacity var(--fast) var(--ease)',
                boxSizing: 'border-box', width: '100%',
              }}
            />
            <button
              className="btn btn-primary"
              onClick={handleSend}
              disabled={isGenerating || !draft.trim() || !available}
              style={{ padding: '0 14px', height: 38, alignSelf: 'flex-end', flexShrink: 0 }}
            >
              {isGenerating
                ? <Icon name="sync" size={14} style={{ animation: 'spin 1s linear infinite' }} />
                : <Icon name="enter" size={14} />}
            </button>
          </div>
        </div>
      </div>

      {/* ── right rail ── */}
      <div style={{ width: 224, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 'var(--s4)' }}>

        {/* context info */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Context</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
            {([
              ['Provider', agentStatus?.provider ?? '—'],
              ['Model',    agentStatus?.model    ?? '—'],
              ['Mode',     agentMode.label],
              ['Messages', String(messages.length)],
              ['Conv',     convId ? convId.slice(0, 8) + '…' : 'none'],
            ] as [string, string][]).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', gap: 'var(--s3)', fontSize: 11 }}>
                <span style={{ width: 60, flexShrink: 0, color: 'var(--txt-3)' }}>{k}</span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--txt-1)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {v}
                </span>
              </div>
            ))}
            <div style={{
              marginTop: 'var(--s2)', paddingTop: 'var(--s2)',
              borderTop: '1px solid var(--line-soft)',
              fontSize: 10.5, color: 'var(--txt-3)', lineHeight: 1.45,
            }}>
              {contextInfo ? (
                <span>
                  Context used:{' '}
                  <span className="mono" style={{ color: 'var(--txt-1)' }}>
                    {contextInfo.used} / {contextInfo.window}
                  </span>{' '}msgs
                </span>
              ) : (
                <span>
                  Context window:{' '}
                  <span className="mono" style={{ color: 'var(--txt-1)' }}>last 10 msgs</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* tool requests — stub */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Tool requests</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-3)', fontStyle: 'italic' }}>
            No pending tool requests
          </div>
          <div style={{
            marginTop: 'var(--s3)', display: 'flex', gap: 6, padding: 'var(--s3)',
            borderRadius: 'var(--r2)', background: 'var(--surface-2)',
            fontSize: 10.5, color: 'var(--txt-3)',
          }}>
            <Icon name="shield" size={11} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 1 }} />
            Tools disabled. Requires NemoClaw/OpenShell.
          </div>
        </div>

        {/* research run — stub */}
        <div className="panel panel-pad">
          <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Research run</div>
          <div style={{ fontSize: 11.5, color: 'var(--txt-3)', fontStyle: 'italic' }}>
            No active research run
          </div>
        </div>

      </div>
    </div>
  );
}
