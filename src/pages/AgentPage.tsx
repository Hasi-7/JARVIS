import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { api, ApiError, streamAgentMessage, isBlockedByMode } from '@/lib/api';
import type { ConversationSummary, AgentToolRequestResponse, AgentStructuredOutput, AgentModePolicy } from '@/lib/api';
import { resolveModePolicy } from '@/lib/agentModes';
import { useRuntimeStatus } from '@/lib/runtimeStatus';
import { RuntimeGuardrailNote } from '@/components/runtime/RuntimeStatus';
import { AGENT_MODES, AGENT_STATES } from '@/data/mock';
import { AgentSphere } from '@/components/ui/AgentSphere';
import { ModeBadge } from '@/components/ui/ModeBadge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Icon } from '@/components/ui/Icon';
import { ToolApprovalQueue } from '@/components/tools/ToolApprovalQueue';

// ── types ─────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id?:         string;
  role:        'user' | 'assistant';
  content:     string;
  timestamp:   string;
  durationMs?: number;
  structured?: AgentStructuredOutput;   // chat-proposed requests; never auto-executed
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

// ── agent tool requests (chat never executes; Assist may queue for review) ──────

const TOOL_OPTIONS = [
  'brain.status', 'brain.raw_status', 'brain.vault_path',
  'brain.today', 'brain.sync_raw', 'vault.create_task', 'calendar.create_candidate',
  'gmail.search', 'gmail.send', 'obsidian.search', 'browser.search', 'shell.run',
];

const APPROVAL_REQUIRED_TOOLS = [
  'brain.today', 'brain.sync_raw', 'vault.create_task', 'calendar.create_candidate',
];

// Only these low-risk read-only brain tools can actually execute (manually, on
// Tool Connections). A request is "reviewable" only when the gateway said so.
const SAFE_LOCAL_TOOLS = ['brain.status', 'brain.raw_status', 'brain.vault_path'];

function isReviewable(tool: string, ev: { allowed: boolean; executionEnabled: boolean }): boolean {
  return ev.executionEnabled === true && ev.allowed === true && SAFE_LOCAL_TOOLS.includes(tool);
}

function decisionTone(decision: string): 'green' | 'amber' | 'red' | 'grey' {
  if (decision === 'allowed') return 'green';
  if (decision === 'requires_approval' || decision === 'not_wired') return 'amber';
  if (decision === 'disabled' || decision === 'denied') return 'red';
  return 'grey';
}

function ChatStructuredPanel({ s, canReview }: { s: AgentStructuredOutput; canReview: boolean }) {
  const navigate = useAppStore((st) => st.navigate);
  const setToolReviewTarget = useAppStore((st) => st.setToolReviewTarget);

  // Blocked by mode — the reply proposed tool requests but the current mode does not
  // allow evaluation. This is NOT a gateway failure; show a clear notice.
  if (s.blockedByMode) {
    return (
      <div style={{ marginTop: 6, padding: '8px 10px', border: '1px solid var(--amber-line, var(--line))', borderRadius: 'var(--r2)', background: 'var(--surface)', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="shield" size={11} style={{ color: 'var(--amber)' }} />
          <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--amber)' }}>Blocked by mode</span>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45 }}>
          {s.message ?? 'This mode does not allow tool requests.'}
        </div>
        <div style={{ fontSize: 9.5, color: 'var(--txt-3)', lineHeight: 1.4 }}>
          The reply proposed tool requests, but they were not evaluated or stored. Switch to Draft,
          Assist, Research, or Escalation to evaluate them. Chat never executes tools; eligible Assist
          requests may enter the authenticated queue for separate approval and execution.
        </div>
      </div>
    );
  }

  if (s.toolRequests.length === 0 && s.parseErrors.length === 0) return null;

  function review(r: AgentToolRequestResponse) {
    // Prefill only — never reconstruct raw args from the sanitized summary, never execute.
    setToolReviewTarget({
      tool: r.tool, argsSummary: r.argsSummary, reason: r.reason ?? undefined,
      requestedBy: r.requestedBy, source: 'agent-chat', relatedId: r.id,
    });
    navigate('tools');
  }

  return (
    <div style={{ marginTop: 6, padding: '8px 10px', border: '1px solid var(--line)', borderRadius: 'var(--r2)', background: 'var(--surface)', display: 'flex', flexDirection: 'column', gap: 5 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield" size={11} style={{ color: 'var(--amber)' }} />
        <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--txt-1)' }}>Structured tool requests detected</span>
      </div>
      {s.toolRequests.map((r) => {
        const ev = r.evaluation;
        const reviewable = isReviewable(r.tool, ev) && canReview;
        return (
          <div key={r.id} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 10.5 }}>
            <StatusDot tone={decisionTone(ev.decision)} />
            <span className="mono" style={{ fontWeight: 600, color: 'var(--txt-0)' }}>{r.tool}</span>
            <span style={{ fontWeight: 600, color: `var(--${decisionTone(ev.decision) === 'green' ? 'green' : decisionTone(ev.decision) === 'red' ? 'red' : decisionTone(ev.decision) === 'amber' ? 'amber' : 'txt-3'})` }}>{ev.decision}</span>
            <span style={{ color: 'var(--txt-3)' }}>risk {ev.riskLevel}</span>
            <span style={{ color: 'var(--txt-3)' }}>exec {String(ev.executionEnabled)}</span>
            <span style={{ color: 'var(--txt-3)' }}>· {r.approvalStatus ?? r.status}</span>
            <span className="mono" style={{ color: 'var(--txt-3)' }}>log {ev.logId.slice(0, 8)}…</span>
            {r.reason && <span style={{ color: 'var(--txt-2)', width: '100%' }}>{r.reason}</span>}
            <div style={{ width: '100%' }}>
              {reviewable ? (
                <button className="btn btn-sm btn-ghost" style={{ fontSize: 10, padding: '2px 7px' }} onClick={() => review(r)}>
                  <Icon name="arrow-right" size={11} /> Review in Tool Connections
                </button>
              ) : (
                <span style={{ fontSize: 9.5, color: 'var(--txt-3)', fontStyle: 'italic' }}>
                  {r.approvalId ? 'Queued below for authenticated operator review' : 'No direct execution from chat'}
                </span>
              )}
            </div>
          </div>
        );
      })}
      {s.parseErrors.map((e, i) => (
        <div key={i} style={{ fontSize: 10, color: 'var(--amber)' }}>{e}</div>
      ))}
      <div style={{ fontSize: 9.5, color: 'var(--txt-3)', lineHeight: 1.4 }}>
        Chat never auto-executes. Eligible Assist requests enter the authenticated queue; approval and execution remain two explicit operator actions.
      </div>
    </div>
  );
}

function AgentToolRequestsPanel({ convId, refreshSignal, modePolicy, canReview, onRequestCreated }: {
  convId: string | null;
  refreshSignal?: number;
  modePolicy: AgentModePolicy;
  canReview: boolean;
  onRequestCreated?: () => void;
}) {
  const navigate = useAppStore((st) => st.navigate);
  const setToolReviewTarget = useAppStore((st) => st.setToolReviewTarget);
  const [tool, setTool]       = useState('brain.status');
  const [reason, setReason]   = useState('');
  const [argsText, setArgsText] = useState('');
  const [requestToken, setRequestToken] = useState('');
  const [busy, setBusy]       = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [blockedNotice, setBlockedNotice] = useState<string | null>(null);
  const [requests, setRequests] = useState<AgentToolRequestResponse[] | null>(null);

  const canEvaluate = modePolicy.canEvaluateToolRequests;
  const needsApprovalToken = modePolicy.id === 'assist' && APPROVAL_REQUIRED_TOOLS.includes(tool.trim());

  const load = useCallback(async () => {
    try {
      const res = await api.listAgentToolRequests({ limit: 20 });
      setRequests(res.requests);
    } catch {
      // non-fatal — leave list as-is
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  // Reload when chat produces new evaluated tool requests.
  useEffect(() => { if (refreshSignal) load(); }, [refreshSignal, load]);
  useEffect(() => { if (!needsApprovalToken) setRequestToken(''); }, [needsApprovalToken]);
  useEffect(() => () => setRequestToken(''), []);

  async function submit() {
    setFormError(null);
    setBlockedNotice(null);
    // Mode gates evaluation. The form is disabled when this is false, but guard anyway.
    if (!canEvaluate) {
      setBlockedNotice(`Tool requests are blocked in ${modePolicy.label} mode.`);
      return;
    }
    if (!tool.trim()) { setFormError('Tool is required.'); return; }
    if (needsApprovalToken && !requestToken) {
      setFormError('This manual Assist request requires the transient operator approval token.');
      return;
    }
    let args: Record<string, unknown> | null = null;
    const raw = argsText.trim();
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setFormError('Args must be a JSON object, e.g. { "query": "…" }.');
          return;
        }
        args = parsed as Record<string, unknown>;
      } catch {
        setFormError('Invalid JSON in args. Fix the syntax or leave it empty.');
        return;
      }
    }
    setBusy(true);
    try {
      const res = await api.createAgentToolRequest({
        tool: tool.trim(), args, reason: reason.trim() || null,
        requestedBy: 'local-agent', conversationId: convId, mode: modePolicy.id,
      }, needsApprovalToken ? requestToken : undefined);
      if (isBlockedByMode(res)) {
        // Backend enforced the block — show a clear notice, not a gateway error.
        setBlockedNotice(res.message);
        return;
      }
      setReason(''); setArgsText(''); setRequestToken('');
      await load();
      onRequestCreated?.();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setRequestToken('');
        setFormError(err.status === 401
          ? 'Approval authentication is required. Re-enter the transient token.'
          : 'The transient approval token was rejected.');
      } else if (err instanceof ApiError && err.status === 503) {
        setFormError(requestToken && err.detail.includes(requestToken)
          ? err.detail.split(requestToken).join('[credential redacted]')
          : err.detail);
      } else {
        setFormError('Failed to create the tool request.');
      }
    } finally {
      setBusy(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--surface-3)', color: 'var(--txt-0)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    fontSize: 11, padding: '5px 7px', boxSizing: 'border-box', fontFamily: 'var(--font-ui)',
  };

  return (
    <div className="panel panel-pad">
      <div className="eyebrow" style={{ marginBottom: 'var(--s3)' }}>Agent Tool Requests</div>
      <div style={{ fontSize: 10.5, color: 'var(--txt-2)', lineHeight: 1.45, marginBottom: 'var(--s3)' }}>
        The Local Agent remains tool-less and chat never auto-executes. Eligible Assist requests can enter
        the authenticated queue below; approval and execution remain separate explicit operator actions.
      </div>

      {/* mode gate — backend-enforced. Blocked modes cannot create requests. */}
      {!canEvaluate && (
        <div style={{ fontSize: 10.5, color: 'var(--amber)', lineHeight: 1.45, marginBottom: 'var(--s3)', padding: '6px 8px', background: 'var(--surface-2)', border: '1px solid var(--line)', borderRadius: 'var(--r2)' }}>
          {modePolicy.available
            ? `${modePolicy.label} mode: structured tool requests are blocked. Switch to Draft, Assist, Research, or Escalation to evaluate them.`
            : `${modePolicy.label} mode is not wired. Tool requests are unavailable.`}
        </div>
      )}

      {/* manual / simulated request form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, opacity: canEvaluate ? 1 : 0.55 }}>
        <select value={tool} onChange={(e) => setTool(e.target.value)} style={inputStyle} disabled={busy || !canEvaluate}>
          {TOOL_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="reason (optional)" style={inputStyle} disabled={busy || !canEvaluate} />
        <textarea
          value={argsText} onChange={(e) => setArgsText(e.target.value)} rows={2} spellCheck={false}
          placeholder='args JSON (optional), e.g. { "query": "x" }'
          disabled={busy || !canEvaluate}
          style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}
        />
        {needsApprovalToken && (
          <label style={{ fontSize: 9.5, color: 'var(--amber)', lineHeight: 1.4 }}>
            Operator token required for this manual Assist request
            <input
              type="password" value={requestToken} autoComplete="off" spellCheck={false}
              onChange={(e) => setRequestToken(e.target.value)} placeholder="BRAIN_UI_APPROVAL_TOKEN"
              disabled={busy || !canEvaluate} style={{ ...inputStyle, marginTop: 4 }}
            />
            <span style={{ display: 'block', marginTop: 3, color: 'var(--txt-3)' }}>Kept in this form's memory only. Structured model requests can instead flow into the queue without exposing a token to chat.</span>
          </label>
        )}
        {formError && (
          <div style={{ fontSize: 10.5, color: 'var(--red)', padding: '4px 6px', background: 'var(--red-bg)', borderRadius: 'var(--r1)', border: '1px solid var(--red-line)' }}>
            {formError}
          </div>
        )}
        {blockedNotice && (
          <div style={{ fontSize: 10.5, color: 'var(--amber)', padding: '4px 6px', background: 'var(--surface-2)', borderRadius: 'var(--r1)', border: '1px solid var(--line)' }}>
            Blocked by mode: {blockedNotice}
          </div>
        )}
        <button className="btn btn-sm btn-primary" onClick={submit} disabled={busy || !canEvaluate || (needsApprovalToken && !requestToken)} style={{ justifyContent: 'center' }}>
          <Icon name="shield" size={12} /> {busy ? 'Evaluating…' : 'Create tool request'}
        </button>
      </div>

      {/* recent requests */}
      <div style={{ marginTop: 'var(--s3)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {requests === null ? (
          <div style={{ fontSize: 10.5, color: 'var(--txt-3)' }}>Loading…</div>
        ) : requests.length === 0 ? (
          <div style={{ fontSize: 10.5, color: 'var(--txt-3)', fontStyle: 'italic' }}>No tool requests yet.</div>
        ) : requests.map((r) => {
          const ev = r.evaluation;
          const effectiveStatus = r.approvalStatus ?? r.status;
          return (
            <div key={r.id} style={{ padding: '6px 7px', border: '1px solid var(--line-soft)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <StatusDot tone={decisionTone(ev.decision)} />
                <span className="mono" style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--txt-0)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.tool}</span>
                <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', color: `var(--${decisionTone(ev.decision) === 'green' ? 'green' : decisionTone(ev.decision) === 'red' ? 'red' : decisionTone(ev.decision) === 'amber' ? 'amber' : 'txt-3'})` }}>
                  {ev.decision}
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, fontSize: 9.5, color: 'var(--txt-3)' }}>
                <span>risk {ev.riskLevel}</span>
                <span>exec {String(ev.executionEnabled)}</span>
                <span>approval {ev.requiresApproval ? 'yes' : 'no'}</span>
                <span>status {effectiveStatus}</span>
                {r.approvalId && <span className="mono">approval {r.approvalId.slice(0, 8)}…</span>}
              </div>
              {r.argsSummary && r.argsSummary !== '(no args)' && (
                <div className="mono" style={{ fontSize: 9.5, color: 'var(--txt-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.argsSummary}</div>
              )}
              <div className="mono" style={{ fontSize: 9, color: 'var(--txt-3)' }}>log {ev.logId.slice(0, 8)}…</div>
              {isReviewable(r.tool, ev) && canReview && (
                <button
                  className="btn btn-sm btn-ghost"
                  style={{ fontSize: 9.5, padding: '2px 6px', alignSelf: 'flex-start' }}
                  onClick={() => {
                    setToolReviewTarget({
                      tool: r.tool, argsSummary: r.argsSummary, reason: r.reason ?? undefined,
                      requestedBy: r.requestedBy, source: 'agent-tool-request', relatedId: r.id,
                    });
                    navigate('tools');
                  }}
                >
                  <Icon name="arrow-right" size={10} /> Review in Tool Connections
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 'var(--s3)', display: 'flex', gap: 6, padding: 'var(--s2) var(--s3)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.4 }}>
        <Icon name="shield" size={11} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 1 }} />
        Chat never auto-executes. Assist approval-required requests move through the authenticated queue below; approve and execute are always separate.
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function AgentPage() {
  const navigate         = useAppStore((s) => s.navigate);
  const agentState       = useAppStore((s) => s.agentState);
  const setAgentState    = useAppStore((s) => s.setAgentState);
  const agentMode        = useAppStore((s) => s.agentMode);
  const setAgentMode     = useAppStore((s) => s.setAgentMode);
  const agentStatus      = useAppStore((s) => s.agentStatus);
  const checkAgentStatus = useAppStore((s) => s.checkAgentStatus);
  const backendConfig    = useAppStore((s) => s.backendConfig);
  const agentPrefill     = useAppStore((s) => s.agentPrefill);
  const setAgentPrefill  = useAppStore((s) => s.setAgentPrefill);
  const agentConvTarget    = useAppStore((s) => s.agentConvTarget);
  const setAgentConvTarget = useAppStore((s) => s.setAgentConvTarget);

  const meta = AGENT_STATES[agentState];

  // ── agent mode policy (backend-enforced, from the global store) ────────────
  const agentModes     = useAppStore((s) => s.agentModes);
  const loadAgentModes = useAppStore((s) => s.loadAgentModes);
  const modePolicy     = resolveModePolicy(agentMode.id, agentModes);

  // OpenClaw / NemoClaw runtime readiness (read-only; static fallback when backend down).
  const runtime = useRuntimeStatus();
  const canEvaluate  = modePolicy.canEvaluateToolRequests;
  const canReview    = modePolicy.canOfferReviewHandoff;
  const modeAvailable = modePolicy.available;

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
  // Structured tool requests from the `structured` SSE event (arrives before `done`)
  const pendingStructuredRef = useRef<AgentStructuredOutput | null>(null);
  // Bumped when chat produces tool requests, so the Tool Requests panel reloads
  const [toolReqRefresh, setToolReqRefresh] = useState(0);

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
  // AgentPage remounts on every navigation to it, so reading the deep-link
  // target here also covers "return to Dashboard, open another conversation".
  useEffect(() => {
    checkAgentStatus();
    // Mode policy is loaded globally on app mount (AppShell). Ensure it's present if
    // this page mounts first or the initial load failed — non-fatal, falls back offline.
    if (!agentModes) loadAgentModes();
    // Deep-link target from Dashboard Recent AI Work — consume once.
    const target = agentConvTarget;
    if (target) setAgentConvTarget(null);
    loadConvList().then((list) => {
      if (list.length === 0) return;
      if (target) {
        if (list.some((c) => c.id === target)) {
          // Selection/state restoration only — no message is sent, no AI call.
          loadConv(target);
        } else {
          // Requested conversation no longer exists — keep the page usable.
          setError('That conversation could not be found. It may have been deleted.');
        }
      } else {
        loadConv(list[0].id);
      }
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
    pendingStructuredRef.current = null;

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

        onStructured: (s) => {
          // Evaluate-only tool requests parsed from the reply. Stored here, attached
          // to the assistant message in onDone; also refresh the Tool Requests panel.
          pendingStructuredRef.current = s;
          setToolReqRefresh((n) => n + 1);
        },

        onDone: async (done) => {
          const full   = streamContentRef.current;
          const ts     = nowHHMM();
          const cid    = resolvedConvIdRef.current;
          const structured = pendingStructuredRef.current ?? undefined;
          pendingStructuredRef.current = null;

          // Commit streaming content to messages
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: full, timestamp: ts, durationMs: done.durationMs, structured },
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
          <div style={{
            marginTop: 'var(--s2)', paddingTop: 'var(--s2)',
            borderTop: '1px solid var(--line-soft)',
            display: 'flex', flexDirection: 'column', gap: 5,
            fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.45,
          }}>
            <div style={{ color: 'var(--txt-2)' }}>
              <span style={{ fontWeight: 600, color: modeAvailable ? 'var(--txt-1)' : 'var(--amber)' }}>
                {modePolicy.label} mode:
              </span>{' '}
              {modePolicy.notes}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <StatusDot tone={!modeAvailable ? 'grey' : canEvaluate ? 'green' : 'amber'} />
                <span>Tool requests: {!modeAvailable ? 'unavailable' : canEvaluate ? 'evaluated; eligible Assist requests may queue' : 'blocked'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <StatusDot tone={canReview ? 'green' : 'grey'} />
                <span>Review handoff: {canReview ? 'allowed (Assist)' : 'not offered'}</span>
              </div>
              {!modeAvailable && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <StatusDot tone="grey" />
                  <span>Mode unavailable / not wired</span>
                </div>
              )}
            </div>
            <div style={{ color: 'var(--txt-3)', fontStyle: 'italic' }}>
              Enforced by backend policy. No mode executes tools from chat — safe-local execution
              stays manual in Tool Connections.
            </div>
          </div>
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
              <ModeBadge mode={agentMode} modes={AGENT_MODES} onSelect={setAgentMode} policy={modePolicy} />
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
                  {msg.role === 'assistant' && msg.structured && <ChatStructuredPanel s={msg.structured} canReview={canReview} />}
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

        {/* Agent requests are mode-gated; Assist approval-required requests may queue. */}
        <AgentToolRequestsPanel convId={convId} refreshSignal={toolReqRefresh} modePolicy={modePolicy} canReview={canReview} onRequestCreated={() => setToolReqRefresh((n) => n + 1)} />

        {/* Assist-mode privileged requests enter this separate manual queue. Chat never executes them. */}
        <ToolApprovalQueue compact onChanged={() => setToolReqRefresh((n) => n + 1)} onOpenLogs={() => navigate('tools')} />

        {/* runtime guardrail — read-only OpenClaw/NemoClaw readiness */}
        <RuntimeGuardrailNote items={runtime.items} />

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
