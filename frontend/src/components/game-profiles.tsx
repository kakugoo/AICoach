"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ApiError, request } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorState, FormField, Input, LoadingState, PageHeader } from "./ui";

type FaceitPlayer = {
  faceit_player_id: string; nickname: string; steam_id64: string | null;
  profile_url: string; avatar_url: string | null; elo: number | null; skill_level: number | null;
};
type SavedPlayer = FaceitPlayer & { id: string; updated_at: string; added_at: string; is_primary: boolean };
type Status = { configured: boolean };

function message(problem: unknown): string {
  const code = problem instanceof ApiError ? problem.status : 0;
  if (code === 404) return "Профиль FACEIT не найден. Проверьте никнейм.";
  if (code === 409) return "Этот профиль уже добавлен в ваш список.";
  if (code === 429) return "Превышен лимит запросов. Попробуйте позже.";
  if (code === 503) return "FACEIT недоступен или ключ API не настроен. Проверьте настройки сервера.";
  if (code === 422) return "Проверьте никнейм: допустимы латинские буквы, цифры, _ и -.";
  if (code === 401) return "Сессия завершилась. Войдите в аккаунт снова.";
  return "Не удалось выполнить запрос. Проверьте соединение и повторите попытку.";
}

function PlayerDetails({ player }: { player: FaceitPlayer }) {
  return <div className="faceit-person"><div className="faceit-person-heading">{player.avatar_url ?
    // FACEIT provides the remote avatar URL; no credentials are sent to it.
    // eslint-disable-next-line @next/next/no-img-element
    <img className="faceit-avatar" src={player.avatar_url} alt="" referrerPolicy="no-referrer" /> : <span className="faceit-avatar faceit-avatar-fallback" aria-hidden="true">{player.nickname.slice(0, 1).toUpperCase()}</span>}
    <div className="faceit-identity"><span className="faceit-label">FACEIT / CS2</span><h3>{player.nickname}</h3><a href={player.profile_url} target="_blank" rel="noopener noreferrer">Открыть профиль FACEIT ↗</a></div></div><dl className="faceit-stats"><div><dt>FACEIT ELO</dt><dd>{player.elo?.toLocaleString("ru-RU") ?? "—"}</dd></div><div><dt>Уровень CS2</dt><dd>{player.skill_level ?? "—"}</dd></div><div><dt>Steam ID64</dt><dd>{player.steam_id64 ?? "Нет данных"}</dd></div></dl></div>;
}

export function GameProfiles() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [profiles, setProfiles] = useState<SavedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<FaceitPlayer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([request<Status>("/game-profiles/status"), request<SavedPlayer[]>("/game-profiles")])
      .then(([status, list]) => { if (active) { setConfigured(status.configured); setProfiles(list); } })
      .catch(problem => { if (active) setError(message(problem)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice(""); setFound(null); setBusy("search");
    try { setFound(await request<FaceitPlayer>(`/game-profiles/search?nickname=${encodeURIComponent(query.trim())}`)); }
    catch (problem) { setError(message(problem)); }
    finally { setBusy(""); }
  }
  async function add() {
    if (!found) return;
    setBusy("add"); setError(""); setNotice("");
    try { const item = await request<SavedPlayer>("/game-profiles", { method: "POST", body: JSON.stringify({ faceit_player_id: found.faceit_player_id }) }); setProfiles(old => [item, ...old]); setFound(null); setNotice("Профиль добавлен в ваш список."); }
    catch (problem) { setError(message(problem)); }
    finally { setBusy(""); }
  }
  async function remove(id: string) {
    setBusy(id); setError(""); setNotice("");
    try { await request<void>(`/game-profiles/${id}`, { method: "DELETE" }); setProfiles(old => old.filter(item => item.id !== id)); setNotice("Профиль удалён из вашего списка."); }
    catch (problem) { setError(message(problem)); }
    finally { setBusy(""); }
  }
  async function primary(id: string, clear: boolean) {
    setBusy(id); setError(""); setNotice("");
    try { await request<void>(`/game-profiles/${id}/primary`, { method: clear ? "DELETE" : "POST" }); setProfiles(await request<SavedPlayer[]>("/game-profiles")); setNotice(clear ? "Основной профиль снят." : "Основной профиль выбран."); }
    catch (problem) { setError(message(problem)); } finally { setBusy(""); }
  }
  async function refresh(id: string) {
    setBusy(id); setError(""); setNotice("");
    try { const item = await request<SavedPlayer>(`/game-profiles/${id}/refresh`, { method: "POST" }); setProfiles(old => old.map(profile => profile.id === id ? item : profile)); setNotice("Данные профиля обновлены."); }
    catch (problem) { setError(message(problem)); }
    finally { setBusy(""); }
  }
  return <><PageHeader title="Игровые профили" description="Отслеживайте публичные профили FACEIT в одном месте."/><div className="profiles-layout"><section className="profiles-search-section"><div className="section-title"><div><h2>Добавить профиль</h2><p>Найдите игрока по точному никнейму FACEIT.</p></div><Badge>FACEIT</Badge></div><Card className="profiles-search-card">{loading ? <LoadingState>Проверяем подключение…</LoadingState> : configured === false ? <div className="profiles-config"><strong>Поиск FACEIT пока не подключён</strong><p>Для поиска настройте серверный API-ключ FACEIT. Сохранённые профили доступны без ключа.</p></div> : configured === true ? <form className="profiles-search-form" onSubmit={search}><FormField label="Никнейм FACEIT" id="faceit-nickname"><Input id="faceit-nickname" placeholder="Например, nickname" value={query} onChange={event => setQuery(event.target.value)} required minLength={1} maxLength={64} pattern="[A-Za-z0-9_-]+" /></FormField><Button type="submit" loading={busy === "search"} disabled={!!busy}>Найти профиль</Button></form> : <p>Не удалось проверить подключение.</p>}<p className="ownership-note">Добавление профиля не подтверждает владение аккаунтом.</p></Card>{error && <ErrorState>{error}</ErrorState>}{notice && <p className="profiles-notice" role="status">{notice}</p>}{found && <Card className="faceit-result"><div className="faceit-card-label"><h3>Результат поиска</h3><Badge>FACEIT</Badge></div><PlayerDetails player={found}/><Button onClick={add} loading={busy === "add"} disabled={!!busy}>Добавить профиль</Button></Card>}</section><section className="profiles-list-section"><div className="section-title"><div><h2>Отслеживаемые профили</h2><p>Информация обновляется по постоянному FACEIT Player ID.</p></div><Badge>{profiles.length}</Badge></div>{loading ? <LoadingState>Загружаем профили…</LoadingState> : profiles.length === 0 ? <Card className="profiles-empty"><EmptyState title="Пока нет профилей" description="Найдите игрока по никнейму, чтобы добавить его в список." /></Card> : <div className="profile-list">{profiles.map(player => <Card key={player.id} className="tracked-card"><PlayerDetails player={player}/>{player.is_primary && <Badge tone="success">Основной профиль</Badge>}<div className="profile-actions"><span>Обновлено: {new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "short"}).format(new Date(player.updated_at))}</span><div><Button variant="secondary" disabled={!!busy} onClick={() => primary(player.id, player.is_primary)}>{player.is_primary ? "Убрать основной" : "Сделать основным"}</Button><Button variant="secondary" disabled={!!busy || !configured} onClick={() => refresh(player.id)}>Обновить</Button><Button variant="ghost" disabled={!!busy} onClick={() => remove(player.id)}>{busy === player.id ? "Подождите…" : "Удалить"}</Button></div></div></Card>)}</div>}</section></div></>;
}
