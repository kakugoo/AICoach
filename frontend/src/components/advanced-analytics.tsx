"use client";
import { Card } from "./ui";

type RoundData = { round: number; side: string; won: boolean | null; kills: number; deaths: number; assists: number | null; damage: number | null; kast: boolean | null; opening_kill: boolean | null; opening_death: boolean | null; trades: number; traded_deaths: number };
type Side = { rounds: number; kills: number; deaths: number; assists: number | null };
type PlayerAnalytics = { rounds: number | null; kd: number | null; kd_difference: number | null; headshot_percent: number | null; kills_per_round: number | null; adr: number | null; kast_percent: number | null; opening_kills: number | null; opening_deaths: number | null; opening_win_percent: number | null; opening_participation_percent: number | null; trades: number | null; traded_deaths: number | null; sides: Record<string, Side | null>; round_details: RoundData[] };
export type Advanced = { version: string; trade_window_ticks?: number; players: Record<string, PlayerAnalytics> };
const value = (n: number | null | undefined, digits = 0) => n == null ? "—" : n.toFixed(digits);

export function AdvancedAnalytics({ data, steamId }: { data: Advanced | null | undefined; steamId: string | null }) {
  const stats = steamId && data?.players[steamId];
  if (!stats) return <Card className="demo-info"><h3>Расширенная статистика</h3><p>Нет проверенных данных. Для старого анализа запустите повторную обработку.</p></Card>;
  return <div className="demo-info"><div className="demo-section-title"><h2>Расширенная статистика</h2><p>Методика {data?.version}. Прочерк означает недостаточно данных или нулевой знаменатель.</p></div>
    <Card><h3>Основные показатели</h3><p>Сыграно раундов: {value(stats.rounds)} · K/D: {value(stats.kd, 2)} · разница K−D: {value(stats.kd_difference)} · попадания в голову: {value(stats.headshot_percent, 1)}% · убийств за раунд: {value(stats.kills_per_round, 2)}</p><p>ADR: {value(stats.adr, 1)} · KAST: {value(stats.kast_percent, 1)}%</p><p className="demo-muted">ADR — урон здоровью противников за подтверждённый сыгранный раунд. KAST — доля раундов с убийством, ассистом, выживанием или разменянной смертью.</p></Card>
    <div className="demo-section-title"><h3>Первые дуэли и размены</h3></div><Card><p>Первые убийства: {value(stats.opening_kills)} · первые смерти: {value(stats.opening_deaths)} · победы в дуэлях: {value(stats.opening_win_percent, 1)}% · участие: {value(stats.opening_participation_percent, 1)}%</p><p>Размены: {value(stats.trades)} · разменянные смерти: {value(stats.traded_deaths)}</p><p className="demo-muted">Размен: союзник убивает убийцу игрока в течение {data?.trade_window_ticks ?? "—"} тиков. Окно и порядок событий влияют на результат.</p></Card>
    <div className="demo-section-title"><h3>Стороны CT / T</h3></div><Card><div className="table-scroll"><table className="demo-table"><thead><tr><th>Сторона</th><th>Раунды</th><th>K</th><th>D</th><th>A</th></tr></thead><tbody>{["CT", "T"].map(side => <tr key={side}><td>{side}</td><td>{value(stats.sides[side]?.rounds)}</td><td>{value(stats.sides[side]?.kills)}</td><td>{value(stats.sides[side]?.deaths)}</td><td>{value(stats.sides[side]?.assists)}</td></tr>)}</tbody></table></div></Card>
    <div className="demo-section-title"><h3>Раунды игрока</h3></div><Card><div className="table-scroll"><table className="demo-table"><thead><tr><th>Раунд</th><th>Сторона</th><th>Результат</th><th>K / D / A</th><th>Урон</th><th>KAST</th></tr></thead><tbody>{stats.round_details.map(r => <tr key={r.round}><td>{r.round}</td><td>{r.side}</td><td>{r.won == null ? "—" : r.won ? "Победа" : "Поражение"}</td><td>{r.kills} / {r.deaths} / {value(r.assists)}</td><td>{value(r.damage)}</td><td>{r.kast == null ? "—" : r.kast ? "Да" : "Нет"}</td></tr>)}</tbody></table></div></Card>
  </div>;
}
