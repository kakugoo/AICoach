"use client";
import { useEffect, useState } from "react";
import { request } from "../lib/api";
import { ErrorState, LoadingState } from "./ui";

type Metric = { value: number | null; count: number; mean: number | null; median: number | null; p25: number | null; p75: number | null; category: "below" | "usual" | "above" | "insufficient" };
type Comparison = { metrics: Record<string, Metric> };
const names: Record<string, string> = { flash: "Flash", smoke: "Smoke", he: "HE", molotov: "Molotov", incendiary: "Incendiary", decoy: "Decoy", blind_enemies: "Ослепления противников", blind_allies: "Ослепления союзников", damage_he_enemy: "HE: урон противникам", damage_fire_enemy: "Огонь: урон противникам" };
const categories = { below: "Ниже обычного", usual: "В обычном диапазоне", above: "Выше обычного", insufficient: "Недостаточно данных" };
const fmt = (n: number | null) => n == null ? "—" : new Intl.NumberFormat("ru-RU", {maximumFractionDigits: 2}).format(n);
export function UtilityComparison({demoId, playerId}: {demoId: string; playerId: string}) {
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { let active = true;
    request<Comparison>(`/demos/${demoId}/comparison?player_id=${encodeURIComponent(playerId)}`).then(data => { if (active) setResult(data); }).catch(() => { if (active) setError(true); });
    return () => { active = false; }; }, [demoId, playerId]);
  if (error) return <ErrorState>Не удалось загрузить сравнение. Откройте вкладку ещё раз.</ErrorState>;
  if (!result) return <LoadingState>Сравниваем с историей…</LoadingState>;
  return <><p className="demo-muted">Текущий матч относительно предыдущих загруженных матчей игрока. Категории описывают частоту, не качество игры.</p><div className="stat-grid">{Object.entries(names).map(([key, label]) => { const m = result.metrics[key]; return <div className={`stat-card comparison-${m.category}`} key={key}><span>{label} / раунд</span><strong>{fmt(m.value)}</strong><small>{categories[m.category]}</small><small>Личный ориентир: {fmt(m.mean)} · матчей: {m.count}{m.p25 != null && m.p75 != null ? ` · диапазон: ${fmt(m.p25)}–${fmt(m.p75)} · медиана: ${fmt(m.median)}` : " · нужно не менее 10"}</small></div>; })}</div></>;
}
