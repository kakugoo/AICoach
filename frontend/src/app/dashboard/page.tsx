"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Matches } from "../../components/matches";
import { GameProfiles } from "../../components/game-profiles";
import { DashboardLayout, type Section } from "../../components/dashboard-layout";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "../../components/ui";
import { ApiError, request, type Profile } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState<Section>("Обзор");
  useEffect(() => {
    let active = true;
    request<Profile>("/auth/me").then(user => { if (active) setProfile(user); }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError("Не удалось загрузить профиль. Проверьте соединение и обновите страницу.");
    });
    return () => { active = false; };
  }, [router]);
  async function logout() {
    setBusy(true); setError("");
    try { await request<void>("/auth/logout", { method: "POST" }); router.replace("/login"); }
    catch { setError("Не удалось выйти. Проверьте соединение и повторите попытку."); setBusy(false); }
  }
  if (!profile) return <main className="loading-page">{error ? <ErrorState>{error}</ErrorState> : <LoadingState>Загружаем личный кабинет…</LoadingState>}</main>;
  return <DashboardLayout section={section} email={profile.email} onSelect={setSection} onLogout={logout} busy={busy}>
    {error && <ErrorState>{error}</ErrorState>}
    {section === "Обзор" ? <><PageHeader title="Обзор" description="Ваше пространство для работы над игрой."/><div className="overview-grid"><div className="overview-primary"><div className="section-title"><div><h2>Ваши матчи</h2><p>История и аналитика появятся здесь.</p></div><Badge>Пока нет матчей</Badge></div><Card className="match-empty"><EmptyState title="Начни с первого матча" description="Загрузите демку в разделе «Мои матчи», чтобы увидеть данные записи."><Button variant="secondary" onClick={() => setSection("Мои матчи")}>Перейти к загрузке</Button></EmptyState></Card><div className="future-heading"><h2>Что появится дальше</h2><span>В РАЗРАБОТКЕ</span></div><div className="future-grid"><Card className="future-card"><span className="future-index">01 / АНАЛИЗ</span><h3>Аналитика матчей</h3><p>Статистика и разбор игровых ситуаций.</p><Badge>В разработке</Badge></Card><Card className="future-card future-ai"><span className="future-index">02 / ИИ</span><h3>Персональный тренер</h3><p>Рекомендации на основе данных матча.</p><Badge tone="ai">В разработке</Badge></Card></div></div><aside className="overview-aside"><Card className="profile-card"><div className="card-heading"><div><h2>Ваш профиль</h2><p>Аккаунт платформы</p></div><span className="profile-avatar" aria-hidden="true">{profile.email.slice(0, 1).toUpperCase()}</span></div><dl><div><dt>Email</dt><dd>{profile.email}</dd></div><div><dt>Дата регистрации</dt><dd>{new Intl.DateTimeFormat("ru-RU", { dateStyle: "long" }).format(new Date(profile.created_at))}</dd></div></dl></Card><div className="aside-note"><span className="note-line"/><p>От данных матча — к пониманию своих решений.</p></div></aside></div></> : section === "Мои матчи" ? <Matches/> : section === "Игровые профили" ? <GameProfiles/> : <><PageHeader title={section} description="Раздел личного кабинета"/><Card className="placeholder-card"><EmptyState title="Раздел в разработке" description="Мы добавим эту возможность на одном из следующих этапов."><Badge tone={section === "ИИ-тренер" ? "ai" : "neutral"}>В разработке</Badge></EmptyState></Card></>}
  </DashboardLayout>;
}
