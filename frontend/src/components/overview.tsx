"use client";
import { useEffect, useState } from "react";
import { request } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "./ui";

type Summary = { total: number; completed: number; processing: number; failed: number; recent: { id: string; original_name: string; created_at: string; status: string; map_name: string | null; score: { teams: {name: string; score: number}[] } | null }[] };
const labels: Record<string, string> = { uploaded: "Загрузка", queued: "В очереди", processing: "Обработка", completed: "Готово", failed: "Ошибка" };
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
  {!summary ? <LoadingState>Загружаем матчи…</LoadingState> : <><div className="summary-grid">{[["Всего загружено", summary.total], ["Анализ готов", summary.completed], ["В обработке", summary.processing], ["Ошибки", summary.failed]].map(([label, n]) => <Card key={label}><span>{label}</span><strong>{n}</strong></Card>)}</div><div className="demo-section-title"><h2>Последние матчи</h2><p>Данные только вашего аккаунта.</p></div>{summary.recent.length ? <div className="demo-list">{summary.recent.map(demo => <Card className="demo-row" key={demo.id}><div className="demo-row-info"><strong>{demo.map_name || demo.original_name}</strong><span>{new Intl.DateTimeFormat("ru-RU", {dateStyle:"medium",timeStyle:"short"}).format(new Date(demo.created_at))} · {demo.score?.teams.map(t => `${t.name} ${t.score}`).join(" : ") || "Счёт недоступен"}</span></div><Badge tone={demo.status === "failed" ? "danger" : demo.status === "completed" ? "success" : "neutral"}>{labels[demo.status] || demo.status}</Badge>{demo.status === "completed" && <Button variant="secondary" onClick={() => onOpen(demo.id)}>Открыть</Button>}</Card>)}</div> : <Card><EmptyState title="Начни с первого матча" description="Загрузите демку, чтобы увидеть статистику и историю игр."><Button onClick={onMatches}>Загрузить демку</Button></EmptyState></Card>}<p className="demo-muted overview-note">Личная статистика появится после подтверждённого выбора игрового профиля.</p></>}
  </>;
}
