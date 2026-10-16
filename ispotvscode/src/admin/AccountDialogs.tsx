// 상담사 계정 관리(AdminApp 의 AccountsView)가 띄우는 창: 확인 · 새 계정 · 임시 비밀번호.
// 모양은 로그인 화면의 '비밀번호 찾기' 창과 같은 틀을 쓴다.

import { useState, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { auth } from "../api/endpoints";
import { ROLE_LABELS, generateInitialPassword, toLocalDateTime } from "../api/adminAdapters";
import type { TemporaryPassword, User, UserRole } from "../api/types";

function Dialog({ title, onClose, children }: { title: string; onClose?: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(15,38,59,0.5)" }}>
      <div role="dialog" aria-modal="true" aria-label={title} className="bg-white rounded-[8px] border border-[#E2E8F0] w-full max-w-md mx-4 overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-[15px] font-semibold text-[#172033]">{title}</h3>
          {onClose && (
            <button type="button" onClick={onClose} aria-label="닫기" className="text-[#94A3B8] hover:text-[#64748B]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          )}
        </div>
        <div className="px-6 py-5 space-y-4">{children}</div>
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 text-[#B91C1C] text-[13px] bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 rounded-[6px]">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <span>{message}</span>
    </div>
  );
}

const CANCEL_BUTTON = "flex-1 py-2.5 border border-[#E2E8F0] text-[#475569] font-semibold rounded-[6px] text-sm hover:bg-[#F8FAFC] transition-colors disabled:opacity-60";
const PRIMARY_BUTTON = "flex-1 py-2.5 bg-[#15314A] hover:bg-[#0F263B] text-white font-semibold rounded-[6px] text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed";
const DANGER_BUTTON = "flex-1 py-2.5 bg-[#B91C1C] hover:bg-[#991B1B] text-white font-semibold rounded-[6px] text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed";

// ── 확인 창 ────────────────────────────────────────────────────────────────
export function ConfirmDialog({
  title, message, confirmLabel, danger, busy, error, onConfirm, onCancel,
}: {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog title={title} onClose={busy ? undefined : onCancel}>
      <div className="text-[13px] text-[#475569] leading-relaxed space-y-2">{message}</div>
      {error && <ErrorBox message={error} />}
      <div className="flex gap-2 pt-1">
        <button type="button" onClick={onCancel} disabled={busy} className={CANCEL_BUTTON}>취소</button>
        <button type="button" onClick={onConfirm} disabled={busy} className={danger ? DANGER_BUTTON : PRIMARY_BUTTON}>
          {busy ? "처리 중..." : confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}

// ── 임시 비밀번호 ──────────────────────────────────────────────────────────
// 임시 비밀번호는 이 응답에서 한 번만 온다(다시 조회할 수 없다). 창을 닫으면 부모가 값을 버린다.
export function TemporaryPasswordDialog({
  title, user, temporary, onClose,
}: {
  title: string;
  user: Pick<User, "name" | "email">;
  temporary: TemporaryPassword;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState<"" | "ok" | "fail">("");

  async function copy() {
    try {
      await navigator.clipboard.writeText(temporary.temporary_password);
      setCopied("ok");
    } catch {
      setCopied("fail");
    }
  }

  return (
    <Dialog title={title}>
      <p className="text-[13px] text-[#475569] leading-relaxed">
        <span className="font-semibold text-[#172033]">{user.name}</span> ({user.email}) 계정의 임시 비밀번호입니다.
        본인에게 안전한 방법으로 전달해 주세요.
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 px-3 py-2.5 rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] font-mono text-[15px] text-[#172033] break-all select-all">
          {temporary.temporary_password}
        </code>
        <button type="button" onClick={copy} className="shrink-0 px-3 py-2.5 border border-[#E2E8F0] rounded-[6px] text-[12px] font-medium text-[#475569] hover:bg-[#F8FAFC]">
          {copied === "ok" ? "복사됨" : "복사"}
        </button>
      </div>
      {copied === "fail" && <p className="text-[12px] text-[#B91C1C]">복사하지 못했습니다. 직접 선택해 복사해 주세요.</p>}
      <ul className="text-[12px] text-[#64748B] leading-relaxed list-disc pl-4 space-y-1">
        <li>사용 기한: {toLocalDateTime(temporary.expires_at)} 까지. 지나면 다시 초기화해야 합니다.</li>
        <li>첫 로그인 때 새 비밀번호로 바꿔야 다른 화면을 쓸 수 있습니다.</li>
        <li className="text-[#B45309] font-medium">이 창을 닫으면 다시 볼 수 없습니다.</li>
      </ul>
      <button type="button" onClick={onClose} className={`w-full ${PRIMARY_BUTTON}`}>확인했습니다 · 닫기</button>
    </Dialog>
  );
}

// ── 새 계정 ────────────────────────────────────────────────────────────────
// 1) 아무도 모르는 임의 비밀번호로 POST /auth/users  2) 곧바로 password-reset 으로 임시 비밀번호 발급.
// 2) 만 실패하면 계정은 만들어진 채로 남는다. 부모가 목록에서 '비밀번호 초기화'를 다시 누르라고 안내한다.
const CREATE_ATTEMPTS = 3;

export function CreateAccountDialog({
  onCreated, onCancel,
}: {
  onCreated: (user: User, temporary: TemporaryPassword | null) => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<UserRole>("COUNSELOR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    if (!email.trim() || !name.trim()) {
      setError("이메일과 이름을 입력해 주세요.");
      return;
    }

    setBusy(true);
    setError(null);

    let created: User | null = null;

    try {
      for (let attempt = 1; attempt <= CREATE_ATTEMPTS && !created; attempt += 1) {
        try {
          created = await auth.createUser({ email: email.trim(), name: name.trim(), role, password: generateInitialPassword() });
        } catch (caught) {
          // 임의 비밀번호에 이메일 아이디 · 이름 조각이 우연히 들어가면 WEAK_PASSWORD 다. 새로 만들어 다시 보낸다.
          if (caught instanceof ApiError && caught.code === "WEAK_PASSWORD" && attempt < CREATE_ATTEMPTS) continue;
          throw caught;
        }
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "계정을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setBusy(false);
      return;
    }

    if (!created) {
      setBusy(false);
      return;
    }

    try {
      const temporary = await auth.resetPassword(created.id);
      onCreated(created, temporary);
    } catch {
      onCreated(created, null);
    }
  }

  const inputClass = "w-full px-3 py-2 rounded-[6px] border border-[#E2E8F0] text-sm text-[#172033] bg-white focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB]";
  const labelClass = "block text-[11px] font-semibold text-[#64748B] uppercase tracking-wider mb-1.5";

  return (
    <Dialog title="신규 계정 생성" onClose={busy ? undefined : onCancel}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="new-email" className={labelClass}>이메일 (로그인 ID)</label>
          <input id="new-email" type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="off" className={inputClass} />
        </div>
        <div>
          <label htmlFor="new-name" className={labelClass}>이름</label>
          <input id="new-name" type="text" value={name} onChange={e => setName(e.target.value)} maxLength={100} autoComplete="off" className={inputClass} />
        </div>
        <div>
          <label htmlFor="new-role" className={labelClass}>역할</label>
          <select id="new-role" value={role} onChange={e => setRole(e.target.value as UserRole)} className={inputClass}>
            {(["COUNSELOR", "ADMIN"] as const).map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
        </div>
        <p className="text-[12px] text-[#64748B] leading-relaxed">
          만들면 임시 비밀번호가 한 번 표시됩니다. 첫 로그인 때 새 비밀번호로 바꾸게 됩니다.
        </p>
        {error && <ErrorBox message={error} />}
        <div className="flex gap-2 pt-1">
          <button type="button" onClick={onCancel} disabled={busy} className={CANCEL_BUTTON}>취소</button>
          <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>{busy ? "만드는 중..." : "계정 만들기"}</button>
        </div>
      </form>
    </Dialog>
  );
}
