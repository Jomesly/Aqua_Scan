import { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, Loader2, TriangleAlert } from 'lucide-react';

export function Card({ title, hint, icon: Icon, actions, children, className = '', flush = false, as: As = 'section' }) {
  return (
    <As className={`card ${flush ? 'flush' : ''} ${className}`}>
      {(title || actions) && (
        <div className={`card-head ${flush ? 'card-pad' : ''}`} style={flush ? { marginBottom: 0 } : undefined}>
          <div>
            {title && (
              <h2>
                {Icon && <Icon size={18} aria-hidden="true" />}
                {title}
              </h2>
            )}
            {hint && <p className="hint">{hint}</p>}
          </div>
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      {children}
    </As>
  );
}

export function Stat({ label, value, unit, title }) {
  return (
    <div className="stat" title={title}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && value !== '—' ? <small>{unit}</small> : null}
      </div>
    </div>
  );
}

const NOTICE_ICONS = { info: Info, warn: TriangleAlert, error: AlertCircle, success: CheckCircle2 };

export function Notice({ kind = 'info', children, role }) {
  const Icon = NOTICE_ICONS[kind];
  return (
    <div className={`notice ${kind}`} role={role || (kind === 'error' ? 'alert' : undefined)}>
      <Icon size={18} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function Empty({ icon: Icon, title, children, action }) {
  return (
    <div className="empty">
      {Icon && <Icon size={36} aria-hidden="true" />}
      <div>
        <strong style={{ color: 'var(--text)' }}>{title}</strong>
        {children && <p className="small" style={{ marginTop: 4 }}>{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ height = 120, style }) {
  return <div className="skeleton" style={{ height, ...style }} aria-hidden="true" />;
}

export function Loading({ label = 'Loading' }) {
  return (
    <div className="grid" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <Skeleton height={36} style={{ width: 240 }} />
      <Skeleton height={180} />
      <Skeleton height={240} />
    </div>
  );
}

export function LoadError({ error, onRetry }) {
  return (
    <Notice kind="error">
      <strong>Could not load this page.</strong> {error?.message}
      {onRetry && (
        <div style={{ marginTop: 8 }}>
          <button className="btn sm" onClick={onRetry} type="button">Try again</button>
        </div>
      )}
    </Notice>
  );
}

export function Button({ busy, children, icon: Icon, className = '', ...props }) {
  return (
    <button className={`btn ${className}`} disabled={busy || props.disabled} aria-busy={busy || undefined} {...props}>
      {busy ? <Loader2 size={18} className="spin" aria-hidden="true" /> : Icon ? <Icon size={18} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function Field({ label, htmlFor, help, error, children }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {help && !error && <span className="help" id={`${htmlFor}-help`}>{help}</span>}
      {error && (
        <span className="error" id={`${htmlFor}-error`}>
          <AlertCircle size={14} aria-hidden="true" /> {error}
        </span>
      )}
    </div>
  );
}

export function Segmented({ name, value, onChange, options, label }) {
  return (
    <div role="radiogroup" aria-label={label} className="segmented">
      {options.map((opt) => {
        const o = typeof opt === 'string' ? { value: opt, label: opt } : opt;
        return (
          <label key={o.value}>
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
            {o.icon ? <o.icon size={16} aria-hidden="true" /> : null}
            <span>{o.label}</span>
          </label>
        );
      })}
    </div>
  );
}

const ToastCtx = createContext(() => {});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-host" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="toast">
            <CheckCircle2 size={18} aria-hidden="true" /> {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
