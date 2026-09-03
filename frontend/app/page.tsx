"use client";

import { useCallback, useEffect, useState } from "react";
import { api, CaseItem, SessionItem } from "@/lib/api";

export default function Home() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selected, setSelected] = useState<CaseItem | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [caseTitle, setCaseTitle] = useState("");
  const [caseDesc, setCaseDesc] = useState("");
  const [sessionTitle, setSessionTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshCases = useCallback(async () => {
    try {
      setCases(await api.listCases());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshCases();
  }, [refreshCases]);

  const selectCase = useCallback(async (c: CaseItem) => {
    setSelected(c);
    try {
      setSessions(await api.listSessions(c.id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  async function submitCase(e: React.FormEvent) {
    e.preventDefault();
    if (!caseTitle.trim()) return;
    try {
      const created = await api.createCase({
        title: caseTitle.trim(),
        description: caseDesc.trim() || undefined,
      });
      setCaseTitle("");
      setCaseDesc("");
      await refreshCases();
      await selectCase(created);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function submitSession(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !sessionTitle.trim()) return;
    try {
      await api.createSession(selected.id, { title: sessionTitle.trim() });
      setSessionTitle("");
      setSessions(await api.listSessions(selected.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          I-SPOT
        </h1>
        <p className="mt-1 text-slate-600">
          아동 상담 사례 · 상담 회차 관리 (개발 환경 데모)
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">사례 (Cases)</h2>

          <form onSubmit={submitCase} className="mb-5 space-y-3">
            <input
              value={caseTitle}
              onChange={(e) => setCaseTitle(e.target.value)}
              placeholder="사례 제목"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500"
            />
            <input
              value={caseDesc}
              onChange={(e) => setCaseDesc(e.target.value)}
              placeholder="설명 (선택)"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500"
            />
            <button
              type="submit"
              className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
            >
              사례 등록
            </button>
          </form>

          {loading ? (
            <p className="text-sm text-slate-500">불러오는 중…</p>
          ) : cases.length === 0 ? (
            <p className="text-sm text-slate-500">
              등록된 사례가 없습니다. 위에서 첫 사례를 등록하세요.
            </p>
          ) : (
            <ul className="space-y-2">
              {cases.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => selectCase(c)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                      selected?.id === c.id
                        ? "border-slate-900 bg-slate-50"
                        : "border-slate-200 hover:border-slate-400"
                    }`}
                  >
                    <span className="font-medium">{c.title}</span>
                    {c.description && (
                      <span className="block text-xs text-slate-500">
                        {c.description}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">
            상담 회차 (Sessions)
            {selected && (
              <span className="ml-2 text-sm font-normal text-slate-500">
                — {selected.title}
              </span>
            )}
          </h2>

          {!selected ? (
            <p className="text-sm text-slate-500">
              왼쪽에서 사례를 선택하면 상담 회차를 관리할 수 있습니다.
            </p>
          ) : (
            <>
              <form onSubmit={submitSession} className="mb-5 flex gap-2">
                <input
                  value={sessionTitle}
                  onChange={(e) => setSessionTitle(e.target.value)}
                  placeholder="회차 제목 (예: 2회차 상담)"
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
                >
                  추가
                </button>
              </form>

              {sessions.length === 0 ? (
                <p className="text-sm text-slate-500">회차가 없습니다.</p>
              ) : (
                <ul className="space-y-2">
                  {sessions.map((s) => (
                    <li
                      key={s.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    >
                      <span className="font-medium">{s.title}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {s.status}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
