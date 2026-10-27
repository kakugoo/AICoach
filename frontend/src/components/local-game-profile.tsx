"use client";

import { useEffect, useState } from "react";
import { request } from "../lib/api";
import { Badge, Button, Card, ErrorState, LoadingState } from "./ui";

type LocalProfile = { nickname: string; steam_id64: string; is_primary: boolean };
type Demo = { id: string; original_name: string; status: string; created_at: string };
type Player = { id: string; name: string; steam_id64: string | null };
type Detail = { match: { map_name: string | null; players: Player[] } | null };

export function LocalGameProfile({ onChange }: { onChange: () => void }) {
  const [local, setLocal] = useState<LocalProfile | null>(null);
  const [demos, setDemos] = useState<Demo[]>([]);
  const [demoId, setDemoId] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [playerId, setPlayerId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function refresh() {
    const [profile, matches] = await Promise.all([request<LocalProfile | null>("/game-profiles/local"), request<Demo[]>("/demos")]);
    setLocal(profile); setDemos(matches.filter(item => item.status === "completed"));
  }
  useEffect(() => { let active = true; Promise.all([request<LocalProfile | null>("/game-profiles/local"), request<Demo[]>("/demos")])
    .then(([profile, matches]) => { if (active) { setLocal(profile); setDemos(matches.filter(item => item.status === "completed")); } })
    .catch(() => { if (active) setError("Не удалось загрузить профили и матчи. Обновите страницу."); })
    .finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  useEffect(() => { const update = () => { refresh().catch(() => setError("Не удалось обновить локальный профиль.")); };
    window.addEventListener("game-profile-changed", update); return () => window.removeEventListener("game-profile-changed", update); }, []);
  useEffect(() => { let active = true; if (!demoId) return;
    request<Detail>(`/demos/${demoId}`).then(data => { if (active) setDetail(data); })
      .catch(() => { if (active) setError("Не удалось открыть матч. Выберите его снова."); });
    return () => { active = false; }; }, [demoId]);
  const player = detail?.match?.players.find(item => item.id === playerId);
  const validSteamId = Boolean(player?.steam_id64 && /^[0-9]{17}$/.test(player.steam_id64));
  async function action(path: string, method: "POST" | "DELETE", body?: object) {
    setBusy(true); setError(""); setNotice("");
    try { await request<void>(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }); await refresh(); onChange(); setNotice(method === "DELETE" ? "Локальная привязка удалена." : "Основной профиль для анализа выбран."); }
    catch { setError("Не удалось сохранить выбор. Проверьте доступ к матчу и повторите попытку."); }
    finally { setBusy(false); }
  }
  return <section className="local-profile-section"><div className="section-title"><div><h2>Выбрать игрока из матча</h2><p>Персонализация без подключения FACEIT.</p></div></div><Card className="local-profile-card">
    {loading ? <LoadingState>Загружаем матчи…</LoadingState> : <>
      {local && <div className="local-profile-current"><strong>{local.nickname}</strong><span>Steam ID64: {local.steam_id64}</span><span>Источник: демка</span>{local.is_primary && <Badge tone="success">Основной профиль для анализа</Badge>}<div className="local-profile-actions">{!local.is_primary && <Button variant="secondary" disabled={busy} onClick={() => action("/game-profiles/local/primary", "POST")}>Сделать основным</Button>}<Button variant="ghost" disabled={busy} onClick={() => action("/game-profiles/local", "DELETE")}>Удалить локальную привязку</Button></div></div>}
      {demos.length === 0 ? <p>Пока нет обработанных матчей. Загрузите демку, чтобы выбрать игрока.</p> : <div className="local-profile-form"><label htmlFor="local-demo">Матч</label><select id="local-demo" value={demoId} onChange={event => { setDemoId(event.target.value); setDetail(null); setPlayerId(""); setError(""); }}><option value="">Выберите матч</option>{demos.map(item => <option key={item.id} value={item.id}>{item.original_name} · {new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(new Date(item.created_at))}</option>)}</select>
      {demoId && !detail && <LoadingState>Загружаем игроков…</LoadingState>}
      {detail?.match && <><label htmlFor="local-player">Игрок</label><select id="local-player" value={playerId} onChange={event => setPlayerId(event.target.value)}><option value="">Выберите игрока</option>{detail.match.players.map(item => <option key={item.id} value={item.id}>{item.name} · {item.steam_id64 || "Steam ID64 недоступен"}</option>)}</select>{player && <p>Steam ID64: {validSteamId ? player.steam_id64 : "недоступен или некорректен — назначение невозможно"}</p>}<Button disabled={busy || !validSteamId} onClick={() => action("/game-profiles/local", "POST", { demo_id: demoId, player_id: playerId })}>Назначить основным игроком</Button></>}</div>}
      <p className="ownership-note">Выбор игрока не подтверждает владение Steam-аккаунтом.</p>
    </>}
    {error && <ErrorState>{error}</ErrorState>}{notice && <p role="status" className="profiles-notice">{notice}</p>}
  </Card></section>;
}
