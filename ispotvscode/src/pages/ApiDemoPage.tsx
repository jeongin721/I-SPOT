// Backend 연결 예시 페이지.
//
// 로그인 → 사례 목록 → 회차 목록까지 실제 API 로 동작한다.
// 다른 화면을 Backend 에 붙일 때 이 파일의 패턴을 그대로 따라 하면 된다.
//
//   1. useEffect 안에서 endpoints 의 함수를 부른다
//   2. loading / error / data 세 가지 상태를 모두 처리한다
//   3. 받은 값은 adapters 로 화면 형태에 맞춘다
//
// 접속: /api-demo

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { cases as casesApi } from "../api/endpoints";
import { deriveStatus, nextAction, toUiCaseWithId, type CaseWithId } from "../api/adapters";
import { useAuth } from "../api/useAuth";
import type { Session } from "../api/types";

export default function ApiDemoPage() {
  const { user, checking, loggingIn, error: authError, login, logout } = useAuth();

  if (checking) {
    return <Centered>로그인 상태를 확인하는 중…</Centered>;
  }

  if (!user) {
    return <LoginForm onLogin={login} loading={loggingIn} error={authError} />;
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center justify-between border-b border-[#E2E8F0] pb-4">
        <div>
          <h1 className="text-[20px] font-semibold text-[#172033]">Backend 연결 확인</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">
            {user.name} · {user.email} · {user.role}
          </p>
        </div>
        <button
          onClick={logout}
          className="px-3 py-2 text-[13px] font-medium text-[#475569] border border-[#CBD5E1] rounded-[6px] hover:bg-[#F1F5F9]"
        >
          로그아웃
        </button>
      </header>

      <CaseList />
    </div>
  );
}

// =========================================================
// 로그인
// =========================================================

function LoginForm({
  onLogin,
  loading,
  error,
}: {
  onLogin: (email: string, password: string) => Promise<unknown>;
  loading: boolean;
  error: string | null;
}) {
  const [email, setEmail] = useState("counselor@ispot.example.com");
  const [password, setPassword] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onLogin(email, password).catch(() => {
      // 오류 메시지는 useAuth 가 error 로 넘겨준다.
    });
  }

  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <form
        onSubmit={handleSubmit}
        className="w-[360px] bg-white border border-[#E2E8F0] rounded-[8px] p-6 space-y-4"
      >
        <div>
          <h1 className="text-[18px] font-semibold text-[#172033]">로그인</h1>
          <p className="text-[13px] text-[#64748B] mt-1">Backend 계정으로 로그인합니다.</p>
        </div>

        <label className="block">
          <span className="text-[13px] font-medium text-[#334155]">이메일</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            className="mt-1 w-full px-3 py-2 text-[14px] border border-[#CBD5E1] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-[#15314A]/20"
          />
        </label>

        <label className="block">
          <span className="text-[13px] font-medium text-[#334155]">비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="mt-1 w-full px-3 py-2 text-[14px] border border-[#CBD5E1] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-[#15314A]/20"
          />
        </label>

        {error && (
          <p className="text-[13px] text-[#B91C1C] bg-[#FEF2F2] border border-[#FECACA] rounded-[6px] px-3 py-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full px-3 py-2 text-[14px] font-medium text-white bg-[#15314A] rounded-[6px] hover:bg-[#0F263B] disabled:opacity-50"
        >
          {loading ? "로그인 중…" : "로그인"}
        </button>
      </form>
    </div>
  );
}

// =========================================================
// 사례 목록
// =========================================================

function CaseList() {
  const [items, setItems] = useState<CaseWithId[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const page = await casesApi.list({ page: 1, size: 50 });

      // 회차 수는 사례 응답에 없으므로 각 사례의 회차 목록에서 total 만 읽어온다.
      const withCounts = await Promise.all(
        page.items.map(async (item) => {
          try {
            const sessions = await casesApi.listSessions(item.id, { page: 1, size: 1 });

            return toUiCaseWithId(item, { sessionCount: sessions.meta.total });
          } catch {
            return toUiCaseWithId(item);
          }
        }),
      );

      setItems(withCounts);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "사례를 불러오지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <Centered>사례를 불러오는 중…</Centered>;

  if (error) {
    return (
      <div className="bg-[#FEF2F2] border border-[#FECACA] rounded-[8px] p-4">
        <p className="text-[14px] text-[#B91C1C]">{error}</p>
        <button
          onClick={load}
          className="mt-3 px-3 py-1.5 text-[13px] font-medium text-[#B91C1C] border border-[#FECACA] rounded-[6px] hover:bg-[#FEE2E2]"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <Centered>
        담당하는 사례가 없습니다. Backend 에서 사례를 먼저 만들어 주세요.
      </Centered>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-[#64748B]">사례 {items.length}건</p>

      {items.map((item) => (
        <div key={item.backendId} className="bg-white border border-[#E2E8F0] rounded-[8px]">
          <button
            onClick={() => setOpenId(openId === item.backendId ? null : item.backendId)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#F8FAFC]"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-medium text-[#172033]">{item.id}</span>
                <span className="text-[13px] text-[#475569]">{item.childName}</span>
                {item.age > 0 && (
                  <span className="text-[12px] text-[#94A3B8]">{item.age}세</span>
                )}
              </div>
              <p className="text-[12px] text-[#94A3B8] mt-0.5">
                담당 {item.counselor} · 회차 {item.sessionCount}건
                {item.lastSession && ` · 최근 상담 ${item.lastSession}`}
              </p>
            </div>
            <span className="text-[12px] text-[#64748B]">
              {openId === item.backendId ? "닫기" : "회차 보기"}
            </span>
          </button>

          {openId === item.backendId && (
            <SessionList caseId={item.backendId} caseNumber={item.id} />
          )}
        </div>
      ))}
    </div>
  );
}

// =========================================================
// 회차 목록
// =========================================================

function SessionList({ caseId, caseNumber }: { caseId: string; caseNumber: string }) {
  const [items, setItems] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);

    casesApi
      .listSessions(caseId, { page: 1, size: 50 })
      .then((page) => {
        if (!cancelled) setItems(page.items);
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(
            caught instanceof ApiError ? caught.message : "회차를 불러오지 못했습니다.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (loading) {
    return <p className="px-4 pb-3 text-[13px] text-[#94A3B8]">회차를 불러오는 중…</p>;
  }

  if (error) {
    return <p className="px-4 pb-3 text-[13px] text-[#B91C1C]">{error}</p>;
  }

  if (items.length === 0) {
    return <p className="px-4 pb-3 text-[13px] text-[#94A3B8]">회차가 없습니다.</p>;
  }

  return (
    <div className="border-t border-[#E2E8F0] divide-y divide-[#F1F5F9]">
      {items.map((session) => {
        const derived = deriveStatus(session.status);

        return (
          <div key={session.id} className="px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-[13px] text-[#172033]">
                {session.session_number}회차
                {session.title && <span className="text-[#64748B]"> · {session.title}</span>}
              </p>
              <p className="text-[12px] text-[#94A3B8] mt-0.5 font-mono">{session.status}</p>
            </div>

            <div className="text-right">
              <span
                className={
                  "inline-block px-2 py-0.5 text-[12px] rounded-[4px] " +
                  (derived.failed
                    ? "bg-[#FEF2F2] text-[#B91C1C]"
                    : session.status === "APPROVED"
                      ? "bg-[#F0FDF4] text-[#15803D]"
                      : "bg-[#F1F5F9] text-[#475569]")
                }
              >
                {derived.label}
              </span>
              <p className="text-[11px] text-[#94A3B8] mt-1">
                다음: {nextAction(session.status)}
              </p>
            </div>
          </div>
        );
      })}

      <p className="px-4 py-2 text-[11px] text-[#CBD5E1]">사례 {caseNumber}</p>
    </div>
  );
}

// =========================================================

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-center py-16 text-[14px] text-[#64748B]">
      {children}
    </div>
  );
}
