import { useState } from 'react';
import type { EntityCreateResponse } from '@/lib/api';

export interface EntityCreateField {
  key: string;
  label: string;
  placeholder: string;
  required?: boolean;
  multiline?: boolean;
}

interface EntityCreateModalProps {
  title: string;
  safetyNote: string;
  fields: EntityCreateField[];
  loading: boolean;
  error: string | null;
  result: EntityCreateResponse | null;
  submitLabel: string;
  onSubmit: (values: Record<string, string>) => void;
  onCancel: () => void;
}

export function EntityCreateModal({
  title,
  safetyNote,
  fields,
  loading,
  error,
  result,
  submitLabel,
  onSubmit,
  onCancel,
}: EntityCreateModalProps) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((field) => [field.key, ''])),
  );
  const [localError, setLocalError] = useState<string | null>(null);

  function set(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    setLocalError(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const missing = fields.find((field) => field.required && !values[field.key]?.trim());
    if (missing) {
      setLocalError(`${missing.label} is required.`);
      return;
    }
    onSubmit(values);
  }

  const fieldStyle: React.CSSProperties = {
    width: '100%', background: 'var(--surface-2)',
    border: '1px solid var(--line)', borderRadius: 'var(--r2)',
    padding: '6px 9px', color: 'var(--txt-0)', fontSize: 12.5,
    fontFamily: 'var(--font-ui)', outline: 'none', boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 10.5, fontWeight: 600, color: 'var(--txt-2)',
    textTransform: 'uppercase', letterSpacing: '0.07em',
    display: 'block', marginBottom: 4,
  };

  const shownError = localError || error;

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div className="panel" style={{
        width: 500, padding: 'var(--s5)',
        display: 'flex', flexDirection: 'column', gap: 'var(--s4)',
        boxShadow: 'var(--shadow-pop)',
        maxHeight: '90vh', overflowY: 'auto',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>{title}</div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
          {fields.map((field) => (
            <div key={field.key}>
              <label style={labelStyle}>
                {field.label} {field.required && <span style={{ color: 'var(--red)' }}>*</span>}
              </label>
              {field.multiline ? (
                <textarea
                  value={values[field.key] ?? ''}
                  onChange={(e) => set(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  style={{ ...fieldStyle, minHeight: 84, resize: 'vertical' }}
                  disabled={loading}
                />
              ) : (
                <input
                  type="text"
                  value={values[field.key] ?? ''}
                  onChange={(e) => set(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  style={fieldStyle}
                  required={field.required}
                  disabled={loading}
                />
              )}
            </div>
          ))}

          <div style={{
            fontSize: 11, color: 'var(--txt-2)',
            padding: 'var(--s2) var(--s3)',
            background: 'var(--surface-2)', borderRadius: 'var(--r2)',
            border: '1px solid var(--line)', lineHeight: 1.5,
          }}>
            {safetyNote}
          </div>

          {shownError && (
            <div style={{
              fontSize: 11.5, color: 'var(--red)',
              padding: 'var(--s2) var(--s3)',
              background: 'var(--red-bg)', borderRadius: 'var(--r2)',
              border: '1px solid var(--red-line)',
            }}>
              {shownError}
            </div>
          )}

          {result && (
            <div style={{
              fontSize: 11.5, color: result.ok ? 'var(--green)' : 'var(--red)',
              padding: 'var(--s2) var(--s3)',
              background: result.ok ? 'var(--green-bg)' : 'var(--red-bg)',
              borderRadius: 'var(--r2)',
              border: `1px solid ${result.ok ? 'var(--green-line)' : 'var(--red-line)'}`,
              display: 'flex', flexDirection: 'column', gap: 6,
            }}>
              <div>{result.ok ? 'Created.' : 'Command failed.'}</div>
              {result.command && <div className="mono">brain {result.command}</div>}
              {result.paths.wikiPath && <div className="mono">{result.paths.wikiPath}</div>}
              {result.paths.rawPath && <div className="mono">{result.paths.rawPath}</div>}
              {result.stdout && <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--txt-1)' }}>{result.stdout}</pre>}
              {result.stderr && <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--txt-1)' }}>{result.stderr}</pre>}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s2)', marginTop: 'var(--s1)' }}>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onCancel} disabled={loading}>
              {result?.ok ? 'Close' : 'Cancel'}
            </button>
            <button type="submit" className="btn btn-sm btn-primary" disabled={loading}>
              {loading ? 'Creating…' : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
