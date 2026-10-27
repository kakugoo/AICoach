import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({ variant = "primary", loading = false, children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; loading?: boolean }) {
  return <button className={`button button--${variant} ${className}`} disabled={props.disabled || loading} {...props}>{loading ? "Подождите…" : children}</button>;
}
export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`} {...props} />;
}
export function FormField({ label, id, hint, children }: { label: string; id: string; hint?: string; children: ReactNode }) {
  return <div className="form-field"><label htmlFor={id}>{label}</label>{children}{hint && <p id={`${id}-hint`} className="field-hint">{hint}</p>}</div>;
}
export function Card({ children, className = "", ...props }: HTMLAttributes<HTMLElement>) { return <section className={`card ${className}`} {...props}>{children}</section>; }
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ai" | "success" | "danger" }) { return <span className={`badge badge--${tone}`}>{children}</span>; }
export function PageHeader({ title, description }: { title: string; description?: string }) { return <div className="page-header"><h1>{title}</h1>{description && <p>{description}</p>}</div>; }
export function EmptyState({ title, description, children }: { title: string; description: string; children?: ReactNode }) { return <div className="empty-state"><div className="empty-symbol" aria-hidden="true"><span/><span/><span/><span/></div><h2>{title}</h2><p>{description}</p>{children}</div>; }
export function LoadingState({ children }: { children: ReactNode }) { return <div className="state-message" role="status">{children}</div>; }
export function ErrorState({ children }: { children: ReactNode }) { return <div className="error-state" role="alert">{children}</div>; }
