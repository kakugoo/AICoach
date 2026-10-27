"use client";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, request } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader } from "./ui";

type Demo = { id: string; original_name: string; size_bytes: number; status: string; error: string | null; created_at: string; completed_at: string | null };
type Player = { id: string; name: string; steam_id64: string | null; team: string | null; kills: number | null; deaths: number | null; assists: number | null; headshots: number | null };
type Round = { number: number; winner: string | null; tick: number | null };
type Match = { map_name: string | null; score: { teams: { name: string; score: number }[] } | null; parser_version: string; analysis_version: string; competitive_rounds: number; round_context: { number: number; winning_team?: string; teams?: { name: string; side: string }[] }[]; players: Player[]; rounds: Round[] };
type Detail = { demo: Demo; match: Match | null };
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const labels: Record<string, string> = { uploaded: "Загрузка", queued: "В очереди", processing: "Обрабатывается", completed: "Готово", failed: "Ошибка" };
function errorMessage(error: unknown): string {
  const status = error instanceof ApiError ? error.status : 0;
  if (status === 413) return "Файл превышает допустимый размер.";
  if (status === 415) return "Поддерживаются файлы .dem и .dem.zst.";
  if (status === 422) return "Файл пустой, повреждён или не является демкой CS2.";
  if (status === 507) return "Недостаточно места в локальном хранилище.";
  if (status === 409) return "Операция сейчас недоступна для этого файла.";
  if (status === 401) return "Сессия завершилась. Войдите снова.";
  return "Не удалось выполнить запрос. Проверьте соединение и повторите попытку.";
}
function sendDemo(file: File, progress: (value: number) => void, signal: AbortSignal): Promise<Demo> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    xhr.open("POST", `${API}/demos?filename=${encodeURIComponent(file.name)}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("X-CSRF-Protection", "1");
    xhr.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100)); };
    xhr.onload = () => { signal.removeEventListener("abort", abort); if (xhr.status >= 200 && xhr.status < 300) { try { resolve(JSON.parse(xhr.responseText) as Demo); } catch { reject(new Error("Invalid response")); } } else reject(new ApiError(xhr.status, "Upload failed")); };
    xhr.onerror = () => { signal.removeEventListener("abort", abort); reject(new Error("Network error")); };
    xhr.onabort = () => { signal.removeEventListener("abort", abort); reject(new Error("Upload cancelled")); };
    signal.addEventListener("abort", abort, { once: true });
    xhr.send(file);
  });
}

export function Matches() {
  const [demos, setDemos] = useState<Demo[]>([]);
  const [maxBytes, setMaxBytes] = useState<number | null>(null);
  const [maxUncompressed, setMaxUncompressed] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selected, setSelected] = useState("");
  const [diagnostics, setDiagnostics] = useState<{facts: {phases: {phase: string; start_tick: number | null; end_tick: number | null}[]; events: {tick: number; excluded: string | null; attacker: string | null; victim: string | null; assister: string | null}[]}} | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState(0);
  const uploadAbort = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const reload = useCallback(async () => { const list = await request<Demo[]>("/demos"); setDemos(list); return list; }, []);
  useEffect(() => {
    let active = true;
    Promise.all([request<Demo[]>("/demos"), request<{max_bytes: number; max_uncompressed_bytes: number}>("/demos/limits")]).then(([list, limits]) => { if (active) { setDemos(list); setMaxBytes(limits.max_bytes); setMaxUncompressed(limits.max_uncompressed_bytes); } }).catch(problem => { if (active) setError(errorMessage(problem)); });
    const timer = window.setInterval(() => { request<Demo[]>("/demos").then(list => { if (active) setDemos(list); }).catch(() => {}); }, 4000);
    return () => { active = false; window.clearInterval(timer); uploadAbort.current?.abort(); };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file) return;
    setError(""); setBusy("upload"); setProgress(0);
    const controller = new AbortController(); uploadAbort.current = controller;
    try { await sendDemo(file, setProgress, controller.signal); setFile(null); if (fileInput.current) fileInput.current.value = ""; await reload(); }
    catch (problem) { setError(errorMessage(problem)); }
    finally { setBusy(""); uploadAbort.current = null; }
  }
  async function open(id: string) { setError(""); setBusy(id); try { const result = await request<Detail>(`/demos/${id}`); setDetail(result); setDiagnostics(null); setSelected(result.match?.players[0]?.id || ""); } catch (problem) { setError(errorMessage(problem)); } finally { setBusy(""); } }
  async function act(id: string, action: "retry" | "remove") { setError(""); setBusy(id); try { await request<void>(`/demos/${id}${action === "retry" ? "/retry" : ""}`, { method: action === "retry" ? "POST" : "DELETE" }); if (detail?.demo.id === id) setDetail(null); await reload(); } catch (problem) { setError(errorMessage(problem)); } finally { setBusy(""); } }
  async function showDiagnostics(id: string) {
    setError("");
    try { setDiagnostics(await request(`/demos/${id}/diagnostics`)); }
    catch (problem) { setError(errorMessage(problem)); }
  }
  const selectedPlayer = detail?.match?.players.find(player => player.id === selected);
  if (detail?.match) return <><Button variant="ghost" onClick={() => setDetail(null)}>← К списку матчей</Button><PageHeader title={detail.match.map_name || "Карта неизвестна"} description={`${detail.demo.original_name} · ${detail.match.score ? detail.match.score.teams.map(team => `${team.name} ${team.score}`).join(" : ") : "счёт недоступен"}`}/><Card className="demo-info"><p>{detail.match.analysis_version === "competitive-2" ? `Соревновательных раундов: ${detail.match.competitive_rounds}. Неподтверждённые данные не отображаются.` : "Устаревший анализ: показатели могут включать разминку. Запустите повторную обработку из списка матчей."}</p><p className="demo-meta">Парсер {detail.match.parser_version} · метод {detail.match.analysis_version}</p></Card><div className="demo-section-title"><h2>Участники</h2></div><Card className="demo-table-card"><div className="table-scroll"><table className="demo-table"><thead><tr><th>Игрок</th><th>Убийства</th><th>Смерти</th><th>Ассисты</th><th>В голову</th><th>K/D</th><th>Команда</th></tr></thead><tbody>{detail.match.players.map(player => <tr key={player.id}><td><button className="player-select" onClick={() => setSelected(player.id)} aria-pressed={selected === player.id}>{player.name}</button></td><td>{player.kills ?? "—"}</td><td>{player.deaths ?? "—"}</td><td>{player.assists ?? "—"}</td><td>{player.headshots ?? "—"}</td><td>{player.kills !== null && player.deaths !== null && player.deaths > 0 ? (player.kills / player.deaths).toFixed(2) : "—"}</td><td>{player.team ?? "—"}</td></tr>)}</tbody></table></div></Card>{selectedPlayer && <Card className="demo-player"><h3>{selectedPlayer.name}</h3><p>Steam ID64: {selectedPlayer.steam_id64 || "нет данных"}</p><p>Убийства: {selectedPlayer.kills ?? "—"} · смерти: {selectedPlayer.deaths ?? "—"} · ассисты: {selectedPlayer.assists ?? "—"} · в голову: {selectedPlayer.headshots ?? "—"}</p></Card>}<div className="demo-section-title"><h2>События окончания раунда</h2><p>Составы и стороны определяются отдельно для каждого раунда.</p></div>{detail.match.rounds.length ? <Card className="demo-table-card"><div className="table-scroll"><table className="demo-table"><thead><tr><th>Раунд</th><th>Победитель</th><th>Сторона</th><th>Тик перехода</th></tr></thead><tbody>{detail.match.rounds.map(round => <tr key={round.number}><td>{round.number}</td><td>{detail.match?.round_context?.find(item => item.number === round.number)?.winning_team ?? "—"}</td><td>{round.winner ?? "—"}</td><td>{round.tick ?? "—"}</td></tr>)}</tbody></table></div></Card> : <p className="demo-muted">Нет доступных событий раундов.</p>}<div className="demo-section-title"><Button variant="secondary" onClick={() => showDiagnostics(detail.demo.id)}>Диагностика обработки</Button></div>{error && <ErrorState>{error}</ErrorState>}{diagnostics && <Card className="demo-info"><h2>Фазы и исключённые события</h2>{diagnostics.facts.phases?.map((phase, i) => <p key={i}>{phase.phase}: {phase.start_tick ?? "?"} — {phase.end_tick ?? "?"}</p>)}<div className="table-scroll"><table className="demo-table"><thead><tr><th>Тик</th><th>Причина исключения</th><th>Убийца / жертва / ассистент (Steam ID)</th></tr></thead><tbody>{diagnostics.facts.events?.filter(event => event.excluded).map((event, i) => <tr key={i}><td>{event.tick}</td><td>{event.excluded}</td><td>{event.attacker ?? "—"} / {event.victim ?? "—"} / {event.assister ?? "—"}</td></tr>)}</tbody></table></div><p>Все исходные события и участники доступны через защищённый диагностический API.</p></Card>}</>;
  return <><PageHeader title="Мои матчи" description="Загружайте демки CS2 для первичного разбора."/><Card className="demo-upload"><div><h2>Загрузить демку</h2><p>Поддерживаются .dem и сжатый формат FACEIT .dem.zst.</p><p>Максимальный размер файла: {maxBytes === null ? "загрузка…" : `${Math.round(maxBytes / 1024 / 1024)} МБ`}; после распаковки: {maxUncompressed === null ? "загрузка…" : `${Math.round(maxUncompressed / 1024 / 1024)} МБ`}.</p></div><form onSubmit={submit} className="demo-upload-form"><label htmlFor="demo-file">Выберите файл</label><input ref={fileInput} id="demo-file" type="file" accept=".dem,.dem.zst" disabled={!!busy} onChange={event => setFile(event.target.files?.[0] || null)} /><Button type="submit" disabled={!file || !!busy || maxBytes === null}>Загрузить демку</Button></form>{busy === "upload" && <div className="demo-progress" role="status"><progress max={100} value={progress}/><span>Загрузка: {progress}%</span></div>}</Card>{error && <ErrorState>{error}</ErrorState>}<div className="demo-section-title"><h2>История загрузок</h2><p>Обработка выполняется отдельным локальным процессом.</p></div>{demos.length === 0 ? <Card><EmptyState title="Пока нет демок" description="Загрузите файл .dem или .dem.zst, чтобы начать анализ."/></Card> : <div className="demo-list">{demos.map(demo => <Card className="demo-row" key={demo.id}><div className="demo-row-info"><strong>{demo.original_name}</strong><span>{new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "short"}).format(new Date(demo.created_at))} · {(demo.size_bytes / 1024 / 1024).toFixed(1)} МБ</span>{demo.error && <p className="demo-error">{demo.error}</p>}</div><Badge tone={demo.status === "failed" ? "danger" : demo.status === "completed" ? "success" : "neutral"}>{labels[demo.status] || demo.status}</Badge><div className="demo-row-actions">{demo.status === "completed" && <Button variant="secondary" disabled={!!busy} onClick={() => open(demo.id)}>Открыть</Button>}{["failed", "completed"].includes(demo.status) && <Button variant="secondary" disabled={!!busy} onClick={() => act(demo.id, "retry")}>Повторить</Button>}{!["uploaded", "processing"].includes(demo.status) && <Button variant="ghost" disabled={!!busy} onClick={() => act(demo.id, "remove")}>Удалить</Button>}</div></Card>)}</div>}</>;
}
