"use client";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, request } from "../lib/api";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader } from "./ui";

type Demo = { id: string; original_name: string; size_bytes: number; status: string; error: string | null; created_at: string; completed_at: string | null };
type Player = { id: string; name: string; steam_id64: string | null; team: string | null; kills: number | null; deaths: number | null; assists: number | null; headshots: number | null };
type Round = { number: number; winner: string | null; tick: number | null };
type Match = { map_name: string | null; score: unknown; parser_version: string; analysis_version: string; players: Player[]; rounds: Round[] };
type Detail = { demo: Demo; match: Match | null };
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const labels: Record<string, string> = { uploaded: "Загрузка", queued: "В очереди", processing: "Обрабатывается", completed: "Готово", failed: "Ошибка" };
function errorMessage(error: unknown): string {
  const status = error instanceof ApiError ? error.status : 0;
  if (status === 413) return "Файл превышает допустимый размер.";
  if (status === 415) return "Поддерживаются только распакованные файлы .dem.";
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
  const [file, setFile] = useState<File | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState(0);
  const uploadAbort = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const reload = useCallback(async () => { const list = await request<Demo[]>("/demos"); setDemos(list); return list; }, []);
  useEffect(() => {
    let active = true;
    Promise.all([request<Demo[]>("/demos"), request<{max_bytes: number}>("/demos/limits")]).then(([list, limits]) => { if (active) { setDemos(list); setMaxBytes(limits.max_bytes); } }).catch(problem => { if (active) setError(errorMessage(problem)); });
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
  async function open(id: string) { setError(""); setBusy(id); try { const result = await request<Detail>(`/demos/${id}`); setDetail(result); setSelected(result.match?.players[0]?.id || ""); } catch (problem) { setError(errorMessage(problem)); } finally { setBusy(""); } }
  async function act(id: string, action: "retry" | "remove") { setError(""); setBusy(id); try { await request<void>(`/demos/${id}${action === "retry" ? "/retry" : ""}`, { method: action === "retry" ? "POST" : "DELETE" }); if (detail?.demo.id === id) setDetail(null); await reload(); } catch (problem) { setError(errorMessage(problem)); } finally { setBusy(""); } }
  const selectedPlayer = detail?.match?.players.find(player => player.id === selected);
  if (detail?.match) return <><Button variant="ghost" onClick={() => setDetail(null)}>← К списку матчей</Button><PageHeader title={detail.match.map_name || "Карта неизвестна"} description={`${detail.demo.original_name} · счёт недоступен`}/><Card className="demo-info"><p>Показаны события всей записи; они могут включать разминку, убийства союзников и неполные раунды. Стороны меняются по ходу матча, поэтому итоговые команды и счёт не определяются.</p><p className="demo-meta">Парсер {detail.match.parser_version} · метод {detail.match.analysis_version}</p></Card><div className="demo-section-title"><h2>Участники</h2></div><Card className="demo-table-card"><div className="table-scroll"><table className="demo-table"><thead><tr><th>Игрок</th><th>Убийства</th><th>Смерти</th><th>Ассисты</th><th>В голову</th></tr></thead><tbody>{detail.match.players.map(player => <tr key={player.id}><td><button className="player-select" onClick={() => setSelected(player.id)} aria-pressed={selected === player.id}>{player.name}</button></td><td>{player.kills ?? "—"}</td><td>{player.deaths ?? "—"}</td><td>{player.assists ?? "—"}</td><td>{player.headshots ?? "—"}</td></tr>)}</tbody></table></div></Card>{selectedPlayer && <Card className="demo-player"><h3>{selectedPlayer.name}</h3><p>Steam ID64: {selectedPlayer.steam_id64 || "нет данных"}</p><p>Убийства: {selectedPlayer.kills ?? "—"} · смерти: {selectedPlayer.deaths ?? "—"} · ассисты: {selectedPlayer.assists ?? "—"} · в голову: {selectedPlayer.headshots ?? "—"}</p></Card>}<div className="demo-section-title"><h2>События окончания раунда</h2><p>Порядок в записи, включая возможную разминку.</p></div>{detail.match.rounds.length ? <Card className="demo-table-card"><div className="table-scroll"><table className="demo-table"><thead><tr><th>№ события</th><th>Победившая сторона</th><th>Тик</th></tr></thead><tbody>{detail.match.rounds.map(round => <tr key={round.number}><td>{round.number}</td><td>{round.winner ?? "—"}</td><td>{round.tick ?? "—"}</td></tr>)}</tbody></table></div></Card> : <p className="demo-muted">Нет доступных событий раундов.</p>}</>;
  return <><PageHeader title="Мои матчи" description="Загружайте демки CS2 для первичного разбора."/><Card className="demo-upload"><div><h2>Загрузить демку</h2><p>Поддерживается распакованный файл .dem. Архив FACEIT сначала распакуйте.</p><p>Максимальный размер: {maxBytes === null ? "загрузка…" : `${Math.round(maxBytes / 1024 / 1024)} МБ`}.</p></div><form onSubmit={submit} className="demo-upload-form"><label htmlFor="demo-file">Выберите файл</label><input ref={fileInput} id="demo-file" type="file" accept=".dem" disabled={!!busy} onChange={event => setFile(event.target.files?.[0] || null)} /><Button type="submit" disabled={!file || !!busy || maxBytes === null}>Загрузить демку</Button></form>{busy === "upload" && <div className="demo-progress" role="status"><progress max={100} value={progress}/><span>Загрузка: {progress}%</span></div>}</Card>{error && <ErrorState>{error}</ErrorState>}<div className="demo-section-title"><h2>История загрузок</h2><p>Обработка выполняется отдельным локальным процессом.</p></div>{demos.length === 0 ? <Card><EmptyState title="Пока нет демок" description="Загрузите распакованную демку CS2, чтобы начать анализ."/></Card> : <div className="demo-list">{demos.map(demo => <Card className="demo-row" key={demo.id}><div className="demo-row-info"><strong>{demo.original_name}</strong><span>{new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "short"}).format(new Date(demo.created_at))} · {(demo.size_bytes / 1024 / 1024).toFixed(1)} МБ</span>{demo.error && <p className="demo-error">{demo.error}</p>}</div><Badge tone={demo.status === "failed" ? "danger" : demo.status === "completed" ? "success" : "neutral"}>{labels[demo.status] || demo.status}</Badge><div className="demo-row-actions">{demo.status === "completed" && <Button variant="secondary" disabled={!!busy} onClick={() => open(demo.id)}>Открыть</Button>}{demo.status === "failed" && <Button variant="secondary" disabled={!!busy} onClick={() => act(demo.id, "retry")}>Повторить</Button>}{!["uploaded", "processing"].includes(demo.status) && <Button variant="ghost" disabled={!!busy} onClick={() => act(demo.id, "remove")}>Удалить</Button>}</div></Card>)}</div>}</>;
}
