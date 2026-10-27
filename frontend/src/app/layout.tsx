import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "CS2 Analytics", description: "Локальная платформа для анализа матчей CS2" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ru"><body>{children}</body></html>;
}
