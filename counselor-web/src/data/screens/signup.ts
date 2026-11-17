// 로그인 화면의 회원가입 팝업 값(디자인 Login.dc.html 의 su* 값). 서버 요청은 useSignup, 이 파일은 단계 · 칸 · 문구만.
//
// 디자인은 이름 → 생년월일 → 성별 → 휴대폰 → 이메일 → 인증번호 → 계정 정보 → 완료다.
// 생년월일 · 성별 · 휴대폰은 받지 않아서(개인정보 최소 저장, API_CONTRACT 3절 '회원가입') 이름 → 이메일 → 인증번호만 남겼다.
// 마지막 단계는 계정이 생기는 것이 아니라 대기 신청이다 — 관리자가 승인해야 로그인할 수 있다.

import type { SignupFailure, SignupState } from "../useSignup";

/** 이름 → 이메일 → 인증번호. */
type Stage = 0 | 1 | 2;

const STAGE_EMAIL: Stage = 1;
const STAGE_CODE: Stage = 2;

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
  /** 틀린 번호 확인창. */
  suWrong: boolean;
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
  suWrong: false,
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
  const busy = signup.busy;
  const can = [name.trim().length > 0, false, code.length === 6 && left > 0][stage] && !busy;

  const send = async () => {
    const cur = getState();
    if (!EMAIL_RE.test(cur.suEmail.trim())) return;
    // 단추는 디자인대로 늘 눌리고, 다시 보낼 수 있는 시간은 여기서 막는다.
    const wait = secondsLeft(cur.suResendAt, Date.now());
    if (wait > 0) {
      setState({ suError: `${wait}초 뒤에 다시 보낼 수 있습니다.` });
      return;
    }
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
      stage: STAGE_CODE,
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
    if (result.remainingAttempts !== undefined && result.remainingAttempts > 0) {
      setState({ suWrong: true });
      return;
    }
    // 쓸 수 있는 번호가 없으면(5분 지남 · 5번 틀림) 이메일 단계로 돌아가 새 번호를 받는다.
    const noCode = result.restart || result.remainingAttempts === 0;
    setState(noCode ? { stage: STAGE_EMAIL, suCode: "", suResendAt: 0, suError: result.message } : { suError: withRetry(result) });
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
      setState({ su: 1, stage: STAGE_EMAIL, suCode: "", suResendAt: 0, suPw: "", suPw2: "", suError: result.message });
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
      if (cur.suName.trim()) setState({ stage: STAGE_EMAIL });
    } else if (cur.stage === STAGE_EMAIL) send();
    else if (cur.stage === STAGE_CODE && cur.suCode.length === 6) check();
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
    suShowEmail: stage >= STAGE_EMAIL,
    suShowCode: stage >= STAGE_CODE,
    suNameCls: stage === 0 ? "on" : "",
    suEmailCls: stage === STAGE_EMAIL ? "on" : stage === STAGE_CODE ? "lock" : "",
    suEmailLock: stage === STAGE_CODE,
    suName: name,
    suEmail: email,
    suCode: code,
    suSetName: (e: { target: { value: string } }) => setState({ suName: e.target.value }),
    suSetEmail: (e: { target: { value: string } }) => {
      if (getState().stage !== STAGE_CODE) setState({ suEmail: e.target.value, suError: "" });
    },
    suSetCode: (e: { target: { value: string } }) =>
      setState({ suCode: String(e.target.value).replace(/[^0-9]/g, "").slice(0, 6) }),
    suKey: onKey,
    suSendOn: stage === STAGE_EMAIL && eOk,
    suSendLabel: stage === STAGE_CODE ? "발송 완료" : "인증번호 받기",
    suResend: send,
    suTimer: mmss,
    suTimerCls: left > 0 ? "sf-time" : "sf-time out",
    suSentNote: left > 0 ? (st.suSent > 1 ? "인증번호를 다시 보냈어요" : `${email.trim()} 로 보냈어요`) : "인증 시간이 지났어요. 다시 보내 주세요.",
    suError: st.suError,
    suNextOn: can,
    suNext: go,
    suWrong: st.suWrong,
    suWrongOk: () => setState({ suWrong: false, suCode: "" }),
    suName2: st.suName2,
    suSetName2: (e: { target: { value: string } }) => setState({ suName2: e.target.value }),
    suPw: pw,
    suPw2: pw2,
    suSetPw: (e: { target: { value: string } }) => setState({ suPw: e.target.value, suErrors: [] }),
    suSetPw2: (e: { target: { value: string } }) => setState({ suPw2: e.target.value }),
    suPwEye: { ...eye(st.suPwV), toggle: () => setState({ suPwV: !getState().suPwV }) },
    suPw2Eye: { ...eye(st.suPw2V), toggle: () => setState({ suPw2V: !getState().suPw2V }) },
    suPwBad: pwBad,
    suPwRuleBad: pw.length > 0 && !passwordOk(pw),
    suErrors: st.suErrors,
    suDoneOn: doneReady,
    suDone: go,
    suClose: close,
    // 신청을 마치고 닫으면 로그인 칸 아래 안내를 띄운다.
    suFinish: () => setState({ ...CLEARED, joined: true }),
  };
}

/** 디자인의 비밀번호 규칙. Backend 규칙보다 좁아서 이것을 지키면 글자 수 · 종류로는 막히지 않는다. 금지 낱말 등은 서버가 사유를 돌려준다. */
function passwordOk(pw: string): boolean {
  const special = /[!"#$%&'()*+,\-./:;<=>?@[\\₩\]^_`{|}~]/;
  const allowed = /^[A-Za-z0-9!"#$%&'()*+,\-./:;<=>?@[\\₩\]^_`{|}~]+$/;

  return pw.length >= 8 && pw.length <= 16 && /[A-Za-z]/.test(pw) && /[0-9]/.test(pw) && special.test(pw) && allowed.test(pw);
}

/** 이름 · 비밀번호 규칙 · 확인이 맞으면 신청할 수 있다. */
function doneOk(st: SignupUi): boolean {
  return st.suName2.trim().length > 0 && passwordOk(st.suPw) && st.suPw2.length > 0 && st.suPw === st.suPw2;
}
