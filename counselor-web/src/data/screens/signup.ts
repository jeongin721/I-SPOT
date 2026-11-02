// 로그인 화면의 회원가입 팝업 값(디자인 Login.dc.html 의 su* 값). 서버 요청은 useSignup, 이 파일은 단계 · 칸 · 문구만.
//
// 디자인은 이름 → 생년월일 → 성별 → 휴대폰 → 이메일 → 인증번호 → 계정 정보 → 완료다.
// 생년월일 · 성별 · 휴대폰은 받지 않기로 해서(개인정보 최소 저장, API_CONTRACT 3절 '회원가입') 이름 → 이메일 → 인증번호만 남겼다.
// 마지막 단계는 계정이 생기는 것이 아니라 대기 신청이다 — 관리자가 승인해야 로그인할 수 있다.

import type { SignupFailure, SignupState } from "../useSignup";

export const SIGNUP_SPAM_NOTE =
  "메일이 오지 않으면 스팸함을 확인하고, 이미 가입했거나 승인을 기다리는 중이면 관리자에게 문의하세요.";

/** 이름 → 이메일 → 인증번호. */
type Stage = 0 | 1 | 2;

export interface SignupUi {
  /** 0 닫힘 · 1 본인 인증 · 2 계정 정보 · 3 신청 접수. */
  su: 0 | 1 | 2 | 3;
  stage: Stage;
  suName: string;
  suEmail: string;
  suCode: string;
  /** 보낸 횟수(문구만 바꾼다). */
  suSent: number;
  suSentAt: number;
  suExpiresIn: number;
  /** 다시 보낼 수 있는 시각(ms). 서버의 resend_after_seconds · retry_after_seconds 로 정한다. */
  suResendAt: number;
  /** 1단계 칸 아래 문구(서버 오류 · 도메인). */
  suError: string;
  /** 틀린 번호 확인창. null 이면 닫힘. */
  suWrong: { title: string; note: string } | null;
  suName2: string;
  suPw: string;
  suPw2: string;
  suPwV: boolean;
  suPw2V: boolean;
  /** 2단계 서버 오류(약한 비밀번호 사유 등). */
  suErrors: string[];
  /** 신청을 마치고 닫으면 로그인 칸 아래 안내를 띄운다. */
  joined: boolean;
}

export const INITIAL_SIGNUP_UI: SignupUi = {
  su: 0,
  stage: 0,
  suName: "",
  suEmail: "",
  suCode: "",
  suSent: 0,
  suSentAt: 0,
  suExpiresIn: 300,
  suResendAt: 0,
  suError: "",
  suWrong: null,
  suName2: "",
  suPw: "",
  suPw2: "",
  suPwV: false,
  suPw2V: false,
  suErrors: [],
  joined: false,
};

/** 팝업을 열 때 · 닫을 때 비우는 값(joined 는 그대로). */
const CLEARED: Omit<SignupUi, "joined"> = { ...INITIAL_SIGNUP_UI };
delete (CLEARED as Partial<SignupUi>).joined;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface SignupValuesInput {
  getState: () => SignupUi;
  setState: (patch: Partial<SignupUi>) => void;
  signup: SignupState;
  now: number;
}

function secondsLeft(at: number, now: number): number {
  return Math.max(0, Math.ceil((at - now) / 1000));
}

function withRetry(failure: SignupFailure): string {
  return failure.retryAfter ? `${failure.message} (${failure.retryAfter}초 뒤)` : failure.message;
}

/**
 * 받는 도메인 목록이 있으면 그 안의 이메일만 보낸다(서버도 422 SIGNUP_EMAIL_DOMAIN_NOT_ALLOWED 로 막는다).
 * 목록은 punycode(xn--…) 꼴이라 한글 도메인은 여기서 비교할 수 없어 서버에 맡긴다.
 */
function domainError(email: string, allowed: string[]): string {
  if (allowed.length === 0) return "";
  const domain = email.trim().toLowerCase().split("@").pop() || "";

  if (/[^\x00-\x7f]/.test(domain)) return "";

  return allowed.includes(domain) ? "" : `${allowed.join(" · ")} 이메일만 가입할 수 있습니다.`;
}

export function signupValues({ getState, setState, signup, now }: SignupValuesInput) {
  const st = getState();
  const { su, stage, suName: name, suEmail: email, suCode: code } = st;
  const eOk = EMAIL_RE.test(email.trim());
  const left = st.suSentAt ? Math.max(0, st.suExpiresIn - Math.floor((now - st.suSentAt) / 1000)) : st.suExpiresIn;
  const resendLeft = secondsLeft(st.suResendAt, now);
  const busy = signup.busy;
  const can = [name.trim().length > 0, eOk && resendLeft === 0, code.length === 6 && left > 0][stage] && !busy;

  const send = async () => {
    const cur = getState();
    if (!EMAIL_RE.test(cur.suEmail.trim()) || secondsLeft(cur.suResendAt, Date.now()) > 0) return;
    const blocked = domainError(cur.suEmail, signup.allowedDomains);
    if (blocked) {
      setState({ suError: blocked });
      return;
    }
    const result = await signup.sendCode(cur.suEmail);
    if (getState().su !== 1) return;
    if (!result.ok) {
      if (!result.message) return;
      setState({
        suError: withRetry(result),
        suResendAt: result.retryAfter ? Date.now() + result.retryAfter * 1000 : getState().suResendAt,
      });
      return;
    }
    const at = Date.now();
    setState({
      stage: 2,
      suCode: "",
      suError: "",
      suSent: getState().suSent + 1,
      suSentAt: at,
      suExpiresIn: result.expiresIn,
      suResendAt: at + result.resendAfter * 1000,
    });
  };

  const check = async () => {
    const cur = getState();
    const result = await signup.verify(cur.suEmail, cur.suCode);
    if (getState().su !== 1) return;
    if (result.ok) {
      setState({ su: 2, suName2: getState().suName, suCode: "", suError: "", suErrors: [] });
      return;
    }
    if (!result.message) return;
    if (result.remainingAttempts !== undefined) {
      setState({
        suWrong: {
          title: "인증번호가 틀렸습니다.",
          note:
            result.remainingAttempts > 0
              ? `${result.remainingAttempts}번 더 틀리면 새 인증번호를 받아야 합니다.`
              : result.message,
        },
      });
      return;
    }
    // 쓸 수 있는 번호가 없으면(5분 지남 · 5번 틀림) 이메일 단계로 돌아가 새 번호를 받는다.
    setState(result.restart ? { stage: 1, suCode: "", suResendAt: 0, suError: result.message } : { suError: withRetry(result) });
  };

  const submit = async () => {
    const cur = getState();
    const result = await signup.submit(cur.suName2, cur.suPw);
    if (getState().su !== 2) return;
    if (result.ok) {
      setState({ ...CLEARED, su: 3 });
      return;
    }
    if (!result.message) return;
    if (result.restart) {
      // 토큰이 30분 지났거나 이미 썼다 — 이메일 인증부터 다시.
      setState({ su: 1, stage: 1, suCode: "", suResendAt: 0, suPw: "", suPw2: "", suError: result.message });
      return;
    }
    setState({ suErrors: result.reasons && result.reasons.length > 0 ? result.reasons : [result.message] });
  };

  const go = () => {
    const cur = getState();
    if (cur.su === 2) {
      if (doneOk(cur)) submit();
      return;
    }
    if (cur.su !== 1 || signup.busy) return;
    if (cur.stage === 0) {
      if (cur.suName.trim()) setState({ stage: 1 });
    } else if (cur.stage === 1) send();
    else if (cur.suCode.length === 6) check();
  };

  // 한글 입력 중 Enter 는 글자가 확정된 뒤에 넘긴다(디자인과 같은 방식).
  const onKey = (e: { key: string; keyCode?: number; nativeEvent?: { isComposing?: boolean }; preventDefault: () => void }) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    if (e.nativeEvent?.isComposing || e.keyCode === 229) setTimeout(go, 30);
    else go();
  };

  const close = () => {
    signup.reset();
    setState({ ...CLEARED });
  };

  const pw = st.suPw;
  const pw2 = st.suPw2;
  const pwBad = pw2.length > 0 && pw !== pw2;
  const doneReady = doneOk(st) && !busy;
  const mmss = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
  const eye = (shown: boolean) => ({
    type: shown ? "text" : "password",
    show: shown,
    pressed: shown ? "true" : "false",
    label: shown ? "비밀번호 숨기기" : "비밀번호 보기",
  });

  return {
    signupOn: signup.enabled,
    joined: st.joined,
    openSignup: () => {
      signup.reset();
      setState({ ...CLEARED, su: 1, joined: false });
    },
    suStep1: su === 1,
    suStep2: su === 2,
    suStep3: su === 3,
    suTitle: ["이름을 입력하세요.", "이메일을 입력하세요.", "이메일로 받은 인증번호 6자리를 입력하세요."][stage],
    suShowName: stage === 0,
    suShowEmail: stage >= 1,
    suShowCode: stage >= 2,
    suNameCls: stage === 0 ? "on" : "",
    suEmailCls: stage === 1 ? "on" : stage === 2 ? "lock" : "",
    suEmailLock: stage === 2,
    suName: name,
    suEmail: email,
    suCode: code,
    suSetName: (e: { target: { value: string } }) => setState({ suName: e.target.value }),
    suSetEmail: (e: { target: { value: string } }) => {
      if (getState().stage !== 2) setState({ suEmail: e.target.value, suError: "" });
    },
    suSetCode: (e: { target: { value: string } }) =>
      setState({ suCode: String(e.target.value).replace(/[^0-9]/g, "").slice(0, 6) }),
    suKey: onKey,
    suSendOn: stage === 1 && eOk && resendLeft === 0 && !busy,
    suSendLabel: stage === 2 ? "발송 완료" : busy && stage === 1 ? "보내는 중…" : resendLeft > 0 ? `${resendLeft}초 뒤` : "인증번호 받기",
    suResend: send,
    suResendOn: resendLeft === 0 && !busy,
    suResendLabel: resendLeft > 0 ? `다시 보내기 (${resendLeft}초)` : "다시 보내기",
    suTimer: mmss,
    suTimerCls: left > 0 ? "sf-time" : "sf-time out",
    suSentNote: left > 0 ? (st.suSent > 1 ? "인증번호를 다시 보냈어요" : `${email.trim()} 로 보냈어요`) : "인증 시간이 지났어요. 다시 보내 주세요.",
    suSpamNote: SIGNUP_SPAM_NOTE,
    suError: st.suError,
    suNextOn: can,
    suNextLabel: busy && stage === 2 ? "확인하는 중…" : "다음",
    suNext: go,
    suWrong: st.suWrong,
    suWrongOk: () => setState({ suWrong: null, suCode: "" }),
    suName2: st.suName2,
    suSetName2: (e: { target: { value: string } }) => setState({ suName2: e.target.value }),
    suPw: pw,
    suPw2: pw2,
    suSetPw: (e: { target: { value: string } }) => setState({ suPw: e.target.value, suErrors: [] }),
    suSetPw2: (e: { target: { value: string } }) => setState({ suPw2: e.target.value }),
    suPwEye: { ...eye(st.suPwV), toggle: () => setState({ suPwV: !getState().suPwV }) },
    suPw2Eye: { ...eye(st.suPw2V), toggle: () => setState({ suPw2V: !getState().suPw2V }) },
    suPwBad: pwBad,
    suErrors: st.suErrors,
    suDoneOn: doneReady,
    suDoneLabel: busy ? "신청하는 중…" : "완료",
    suDone: go,
    suClose: close,
    // 신청을 마치고 닫으면 로그인 칸 아래 안내를 띄운다.
    suFinish: () => setState({ ...CLEARED, joined: true }),
  };
}

/** 이름 · 비밀번호(8자 이상) · 확인이 맞으면 신청할 수 있다. 나머지 규칙은 서버가 보고 사유를 돌려준다. */
function doneOk(st: SignupUi): boolean {
  return st.suName2.trim().length > 0 && st.suPw.length >= 8 && st.suPw2.length > 0 && st.suPw === st.suPw2;
}
