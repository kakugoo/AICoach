"use client";
import { useEffect, useState } from "react";
import { request } from "../lib/api";
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "./ui";

type Recent = { id: string; original_name: string; created_at: string; status: string; map_name: string | null; score: { teams: {name: string; score: number}[] } | null; personal: {outcome: "win" | "loss" | "draw" | null; score: [number, number] | null} | null };
type Summary = { total: number; completed: number; processing: number; failed: number; recent: Recent[] };
const labels: Record<string, string> = { uploaded: "Загрузка", queued: "В очереди", processing: "Обработка", completed: "Готово", failed: "Ошибка" };
const outcomes: Record<string, string> = { win: "Победа", loss: "Поражение", draw: "Ничья" };
function MatchContents({ demo }: {demo: Recent}) {
  const score = demo.personal?.score || demo.score?.teams.map(t => t.score);
  const outcome = demo.personal?.outcome;
  return <><span className="overview-match-main"><strong className={`overview-score ${outcome || "unknown"}`}>{demo.status === "completed" ? score?.join(" : ") || "Счёт неизвестен" : labels[demo.status] || demo.status}</strong>{demo.status === "completed" && <span className="overview-map"> / {demo.map_name?.replace(/^de_/, "") || "Карта неизвестна"}</span>}</span><span className="overview-match-meta">Загружено {new Intl.DateTimeFormat("ru-RU", {dateStyle:"long",timeStyle:"short"}).format(new Date(demo.created_at))} · {outcome ? outcomes[outcome] : demo.status === "completed" ? "Команда профиля не определена" : labels[demo.status] || demo.status}</span></>;
}
export function Overview({ onMatches, onProfile, onOpen }: { onMatches: () => void; onProfile: () => void; onOpen: (id: string) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    const load = () => request<Summary>("/demos/summary").then(data => { if (active) { setSummary(data); setError(false); } }).catch(() => { if (active) setError(true); });
    load(); const timer = window.setInterval(load, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  return <><PageHeader title="Обзор" description="Ваши матчи и состояние обработки."/><div className="overview-actions"><Button onClick={onMatches}>Загрузить демку</Button><Button variant="secondary" onClick={onMatches}>Все матчи</Button><Button variant="ghost" onClick={onProfile}>Игровые профили</Button></div>
  {error && <ErrorState>Не удалось загрузить матчи. Проверьте соединение; повторим запрос автоматически.</ErrorState>}
  {!summary ? <LoadingState>Загружаем матчи…</LoadingState> : <><div className="summary-grid">{[["Всего матчей", summary.total], ["Проанализировано", summary.completed], ["В обработке", summary.processing], ["Ошибки анализа", summary.failed]].map(([label, n]) => <Card key={label}><span>{label}</span><strong>{n}</strong></Card>)}</div><div className="demo-section-title"><h2>Последние матчи</h2><p>Данные только вашего аккаунта.</p></div>{summary.recent.length ? <div className="demo-list">{summary.recent.map(demo => demo.status === "completed" ? <button type="button" className="overview-match" key={demo.id} onClick={() => onOpen(demo.id)}><MatchContents demo={demo}/></button> : <div className="overview-match overview-match-static" key={demo.id}><MatchContents demo={demo}/></div>)}</div> : <Card><EmptyState title="Начни с первого матча" description="Загрузите демку, чтобы увидеть статистику и историю игр."><Button onClick={onMatches}>Загрузить демку</Button></EmptyState></Card>}<p className="demo-muted overview-note">Основной профиль используется для сопоставления по Steam ID64 и не подтверждает владение аккаунтом.</p></>}
  </>;
}
