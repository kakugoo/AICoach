"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brand } from "../components/dashboard-layout";

type Connection = "checking" | "ready" | "database-error" | "offline";
const labels: Record<Connection, string> = { checking: "Проверяем соединение", ready: "Система готова", "database-error": "База данных недоступна", offline: "Сервер недоступен" };

export default function Home() {
  const [status, setStatus] = useState<Connection>("checking");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/ready`, { signal: controller.signal, cache: "no-store" })
      .then(response => { if (active) setStatus(response.ok ? "ready" : response.status === 503 ? "database-error" : "offline"); })
      .catch(() => { if (active) setStatus("offline"); })
      .finally(() => window.clearTimeout(timer));
    return () => { active = false; controller.abort(); window.clearTimeout(timer); };
  }, [attempt]);

  return <main className="public-shell"><header className="public-header"><Brand/><nav className="home-nav" aria-label="Аккаунт"><Link href="/login">Войти</Link><Link className="public-cta" href="/register">Создать аккаунт <span aria-hidden="true">↗</span></Link></nav></header><section className="public-intro"><div><p className="public-label">CS2 ANALYTICS / ЛОКАЛЬНАЯ ВЕРСИЯ</p><h1>Игра становится<br/><em>понятнее.</em></h1><p className="public-lead">Основа для вдумчивого разбора матчей Counter-Strike 2. От игровых данных — к решениям, которые помогают расти.</p><div className="public-actions"><Link className="button button--primary" href="/register">Создать аккаунт <span aria-hidden="true">↗</span></Link><Link className="text-link" href="/login">Уже есть аккаунт? Войти</Link></div></div><div className="public-visual" aria-hidden="true"><div className="visual-top"><span>TACTICAL INTELLIGENCE</span><span>CS2</span></div><div className="visual-center"><div className="visual-target"><span/><span/></div><div className="visual-copy"><strong>ANALYZE<br/>YOUR GAME.</strong><small>ДАННЫЕ · КОНТЕКСТ · ПРОГРЕСС</small></div></div><div className="visual-bottom"><span>АНАЛИТИЧЕСКАЯ ПЛАТФОРМА</span><span>LOCAL / 2026</span></div></div></section><section className="system" aria-labelledby="system-title"><div className="system-heading"><div><h2 id="system-title">Состояние системы</h2><p>Проверка соединения с сервером и базой данных.</p></div><button className="button button--secondary" onClick={() => { setStatus("checking"); setAttempt(value => value + 1); }} disabled={status === "checking"}>Проверить снова</button></div><div className="status-row" role="status" aria-live="polite"><span className={`status-dot ${status}`}/><div><strong>{labels[status]}</strong><p>{status === "ready" ? "Сервер отвечает, соединение с базой установлено." : status === "database-error" ? "Запустите PostgreSQL и повторите проверку." : status === "offline" ? "Запустите backend и повторите проверку." : "Подключаемся к локальному серверу."}</p></div><span className="status-code">{status === "ready" ? "ONLINE" : status === "checking" ? "CHECK" : "OFFLINE"}</span></div></section><footer className="public-footer"><span>CS2 ANALYTICS</span><span>Основа проекта · локальная разработка</span></footer></main>;
}
