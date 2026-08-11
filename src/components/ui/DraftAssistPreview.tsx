import type { DraftAssistModelTier } from '@/lib/api';
import { useAppStore } from '@/store/useAppStore';

export interface DraftAssistPreviewRow {
  label: string;
  value: unknown;
}

interface DraftAssistPreviewProps {
  modelTier: DraftAssistModelTier;
  onModelTierChange: (tier: DraftAssistModelTier) => void;
  onRequest: () => void;
  requesting: boolean;
  disabled: boolean;
  preview: { modelTier: DraftAssistModelTier; model: string; durationMs: number } | null;
  rows: DraftAssistPreviewRow[];
  stale: boolean;
  error: string | null;
  onApply: () => void;
  onDismiss: () => void;
}

function displayValue(value: unknown): string {
  if (value === null) return '(clear)';
  if (Array.isArray(value)) {
    if (value.length === 0) return '(empty list)';
    return value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  }
  if (value === '') return '(empty)';
  return String(value);
}

export function DraftAssistPreview({
  modelTier, onModelTierChange, onRequest, requesting, disabled,
  preview, rows, stale, error, onApply, onDismiss,
}: DraftAssistPreviewProps) {
  const agentStatus = useAppStore((state) => state.agentStatus);
  const everydayUnavailable = agentStatus?.everydayAvailable === false;
  const heavyUnavailable = agentStatus?.heavyAvailable === false;
  const selectedUnavailable = modelTier === 'everyday' ? everydayUnavailable : heavyUnavailable;

  return (
    <div style={{ padding: 'var(--s3)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s2)' }}>
        <div>
          <label style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)', textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', marginBottom: 4 }}>
            AI model tier
          </label>
          <select
            value={modelTier}
            onChange={(e) => onModelTierChange(e.target.value as DraftAssistModelTier)}
            disabled={disabled || requesting}
            style={{ background: 'var(--surface-1)', border: '1px solid var(--line)', borderRadius: 'var(--r2)', padding: '5px 8px', color: 'var(--txt-0)', fontSize: 12 }}
          >
            <option value="everyday" disabled={everydayUnavailable}>Everyday{everydayUnavailable ? ' (not installed)' : ''}</option>
            <option value="heavy" disabled={heavyUnavailable}>Heavy{heavyUnavailable ? ' (not installed)' : ''}</option>
          </select>
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={onRequest} disabled={disabled || requesting || selectedUnavailable}>
          {requesting ? 'Generating preview…' : 'AI assist (preview)'}
        </button>
      </div>

      <div style={{ fontSize: 10.5, color: 'var(--txt-3)', lineHeight: 1.45 }}>
        Opt-in and preview-only. Suggestions stay separate until you apply them; applying does not save the draft or write to the vault.
      </div>

      {selectedUnavailable && (
        <div style={{ fontSize: 11.5, color: 'var(--amber)' }}>
          This model tier is not installed in Ollama. Refresh Local Agent status after pulling it.
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11.5, color: 'var(--red)', padding: 'var(--s2)', background: 'var(--red-bg)', borderRadius: 'var(--r2)', border: '1px solid var(--red-line)' }}>
          {error}
        </div>
      )}

      {preview && (
        <div style={{ borderTop: '1px solid var(--line-soft)', paddingTop: 'var(--s2)', display: 'flex', flexDirection: 'column', gap: 'var(--s2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--s2)', fontSize: 10.5, color: 'var(--txt-2)' }}>
            <strong style={{ color: 'var(--txt-1)' }}>Proposed fields</strong>
            <span className="mono">{preview.modelTier} · {preview.model} · {preview.durationMs} ms</span>
          </div>
          {rows.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--txt-3)' }}>No editable suggestions were returned.</div>
          ) : (
            <div style={{ display: 'grid', gap: 5 }}>
              {rows.map((row) => (
                <div key={row.label} style={{ display: 'grid', gridTemplateColumns: '130px minmax(0, 1fr)', gap: 'var(--s2)', fontSize: 11, lineHeight: 1.4 }}>
                  <span style={{ color: 'var(--txt-3)' }}>{row.label}</span>
                  <span style={{ color: 'var(--txt-1)', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 76, overflow: 'auto' }}>{displayValue(row.value)}</span>
                </div>
              ))}
            </div>
          )}
          {stale && (
            <div style={{ fontSize: 11.5, color: 'var(--amber)', padding: 'var(--s2)', background: 'var(--amber-bg)', border: '1px solid var(--amber-line)', borderRadius: 'var(--r2)' }}>
              This preview is stale because the draft or local form changed. Save changes if needed, then request a new preview.
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)' }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onDismiss} disabled={requesting}>Dismiss</button>
            <button type="button" className="btn btn-sm btn-primary" onClick={onApply} disabled={requesting || stale || rows.length === 0}>Apply preview to form</button>
          </div>
        </div>
      )}
    </div>
  );
}
