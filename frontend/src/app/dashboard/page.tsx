"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Overview } from "../../components/overview";
import { Matches } from "../../components/matches";
import { GameProfiles } from "../../components/game-profiles";
import { DashboardLayout, type Section } from "../../components/dashboard-layout";
import { Badge, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "../../components/ui";
import { ApiError, request, type Profile } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedDemo, setSelectedDemo] = useState<string | null>(null);
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
    {section === "Обзор" ? <Overview onMatches={() => { setSelectedDemo(null); setSection("Мои матчи"); }} onProfile={() => setSection("Игровые профили")} onOpen={id => { setSelectedDemo(id); setSection("Мои матчи"); }}/> : section === "Мои матчи" ? <Matches initialDemoId={selectedDemo}/> : section === "Игровые профили" ? <GameProfiles/> : <><PageHeader title={section} description="Раздел личного кабинета"/><Card className="placeholder-card"><EmptyState title="Раздел в разработке" description="Мы добавим эту возможность на одном из следующих этапов."><Badge tone={section === "ИИ-тренер" ? "ai" : "neutral"}>В разработке</Badge></EmptyState></Card></>}
  </DashboardLayout>;
}
