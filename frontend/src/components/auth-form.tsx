"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError, request, type Profile } from "../lib/api";
import { Brand } from "./dashboard-layout";
import { Button, ErrorState, FormField, Input } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const register = mode === "register";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (register && password !== confirmation) { setError("Пароли не совпадают."); return; }
    setBusy(true);
    try {
      await request<Profile>(`/auth/${mode}`, { method: "POST", body: JSON.stringify({ email, password }) });
      router.replace("/dashboard");
    } catch (problem) {
      const status = problem instanceof ApiError ? problem.status : 0;
      setError(status === 409 ? "Этот email уже зарегистрирован." : status === 401 ? "Неверный email или пароль." : status === 429 ? "Слишком много попыток. Попробуйте через 15 минут." : status === 422 ? "Проверьте email и пароль." : "Не удалось связаться с сервером. Попробуйте ещё раз.");
    } finally { setBusy(false); }
  }
  return <main className="auth-layout"><header className="auth-top"><Brand/><Link className="back-link" href="/">На главную <span aria-hidden="true">↗</span></Link></header><section className="auth-content"><div className="auth-title"><p className="auth-kicker">CS2 ANALYTICS / АККАУНТ</p><h1>{register ? "Создать аккаунт" : "С возвращением"}</h1><p>{register ? "Создайте аккаунт, чтобы начать работу с платформой." : "Войдите, чтобы продолжить работу с платформой."}</p></div><form onSubmit={submit} className="auth-form"><FormField label="Email" id="email"><Input id="email" type="email" autoComplete="email" required maxLength={320} value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" /></FormField><FormField label="Пароль" id="password" hint={register ? "Не менее 12 символов." : undefined}><Input id="password" type="password" autoComplete={register ? "new-password" : "current-password"} required minLength={register ? 12 : 1} maxLength={256} value={password} onChange={e => setPassword(e.target.value)} aria-describedby={register ? "password-hint" : undefined} /></FormField>{register && <FormField label="Подтвердите пароль" id="confirmation"><Input id="confirmation" type="password" autoComplete="new-password" required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></FormField>}{error && <ErrorState>{error}</ErrorState>}<Button loading={busy} type="submit" className="auth-submit">{register ? "Создать аккаунт" : "Войти"}<span aria-hidden="true">↗</span></Button></form><p className="auth-switch">{register ? "Уже есть аккаунт? " : "Нет аккаунта? "}<Link href={register ? "/login" : "/register"}>{register ? "Войти" : "Зарегистрироваться"}</Link></p></section><footer className="auth-footer"><span>CS2 ANALYTICS</span><span>Локальная версия</span></footer></main>;
}
