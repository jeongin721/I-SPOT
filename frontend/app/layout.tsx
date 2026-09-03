import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "I-SPOT",
  description: "AI 상담 기록 보조 — 사례 및 상담 회차 관리",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
