"use client";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Button } from "./ui";

export const sections = ["Обзор", "Мои матчи", "Аналитика", "ИИ-тренер", "Тренировки", "Игровые профили", "Настройки"] as const;
export type Section = typeof sections[number];
const icons: Record<Section, ReactNode> = {
  "Обзор": <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  "Мои матчи": <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
  "Аналитика": <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
  "ИИ-тренер": <><path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2L12 3z"/><path d="M19 16v4m-2-2h4"/></>,
  "Тренировки": <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12l7-7"/></>,
  "Игровые профили": <><circle cx="12" cy="8" r="3"/><path d="M5 20c0-4 3-6 7-6s7 2 7 6"/></>,
  "Настройки": <><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/></>,
};
export function Brand() { return <Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">C<span>2</span></span><span className="brand-name">CS2 <strong>ANALYTICS</strong><small>TACTICAL INTELLIGENCE</small></span></Link>; }
export function Sidebar({ section, onSelect, open }: { section: Section; onSelect: (s: Section) => void; open: boolean }) {
  return <aside id="dashboard-navigation" className={`sidebar ${open ? "sidebar--open" : ""}`}><div className="sidebar-brand"><Brand /></div><p className="sidebar-label">РАБОЧЕЕ ПРОСТРАНСТВО</p><nav aria-label="Разделы кабинета">{sections.map(item => <button key={item} type="button" className={`nav-item ${section === item ? "nav-item--active" : ""}`} onClick={() => onSelect(item)} aria-current={section === item ? "page" : undefined}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[item]}</svg><span>{item}</span></button>)}</nav><div className="sidebar-bottom"><span className="sidebar-indicator"/>Локальная версия</div></aside>;
}
export function Topbar({ section, email, onSettings, onLogout, busy, open, onToggle }: { section: Section; email: string; onSettings: () => void; onLogout: () => void; busy: boolean; open: boolean; onToggle: () => void }) {
  return <header className="dashboard-topbar"><Button variant="ghost" className="menu-toggle" onClick={onToggle} aria-expanded={open} aria-controls="dashboard-navigation" aria-label={open ? "Закрыть меню" : "Открыть меню"}><span aria-hidden="true">☰</span></Button><div className="topbar-title"><span>ЛИЧНЫЙ КАБИНЕТ</span><strong>{section}</strong></div><div className="topbar-account"><div className="account-label"><span>АККАУНТ</span><strong title={email}>{email}</strong></div><Button variant="ghost" onClick={onSettings}>Настройки</Button><Button variant="secondary" onClick={onLogout} loading={busy}>Выйти</Button></div></header>;
}
export function DashboardLayout({ section, email, onSelect, onLogout, busy, children }: { section: Section; email: string; onSelect: (s: Section) => void; onLogout: () => void; busy: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const select = (item: Section) => { onSelect(item); setOpen(false); };
  return <div className="dashboard-layout"><Sidebar section={section} onSelect={select} open={open}/><div className="dashboard-main"><Topbar section={section} email={email} onSettings={() => select("Настройки")} onLogout={onLogout} busy={busy} open={open} onToggle={() => setOpen(!open)}/><main id="main-content" className="dashboard-content">{children}</main></div></div>;
}
