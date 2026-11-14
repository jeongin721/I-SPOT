// 상담사 앱(폰) · 상담 전 브리핑(읽기 전용)
// 원본: 앱 · 상담 전 브리핑 (읽기 전용 · 확인할 사항 체크) 2026-11-10 zip 의 AppBrief.dc.html
//
// 서버 연결: 주소 ?case=<사례 ID>. 웹 사례 상세의 상담 전 브리핑과 **같은 값**(preBriefingValues)을 폰 모양으로 보인다.
//  - 먼저 볼 것: 아이가 보낸 말 · 체크인 응답 변화(콩콩 아이 앱) · 처음 나온 이야기(분석이 끝난 최근 회차의 새 주제, AI 제안).
//  - 확인할 사항: 웹과 같은 목록. 체크는 서버 칸이 없어 이 폰에만 회차별로 기억한다(웹과 같은 저장 이름, 기기마다 따로).
//  - 추가 질문: 그 회차에서 상담사가 승인한 질문만(승인 전 AI 초안은 안 보임).
//  - 머리 위 줄: 이 사례의 가장 가까운 상담 일정(오늘이면 '오늘 16:00') · 다음 회차 번호. 일정이 없으면 회차 번호만.
//  - '이 상담 녹음 시작' 은 그 아이를 골라 둔 채 앱 · 녹음으로 간다.
// 브리핑 내용 수정 · 질문 편집은 웹에서 한다(디자인 문구 그대로).
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { childApp } from '../api/endpoints';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { latestAnalyzedSession, useCaseSignals } from '../data/useCaseSignals';
import { useFollowupChecklist } from '../data/useFollowupChecklist';
import { useFollowupChecks } from '../data/useFollowupChecks';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { useSignalHistory } from '../data/useSignalHistory';
import { signedIn } from '../data/screens/common';
import { checklistNeedsEvidence } from '../data/screens/followupQ';
import { preBriefingValues } from '../data/screens/preBriefing';
import { useRemote } from '../data/useRemote';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { addDays, parseYmd, useAppSchedule, ymd } from '../data/useAppSchedule';

function useBrief(caseId) {
  const session = useAuthSession();
  const on = signedIn(session) && !!caseId;
  const detail = useCaseDetail(caseId, { enabled: on });
  const briefSessionId = latestAnalyzedSession(detail.sessions)?.id ?? null;
  const checks = useFollowupChecks(briefSessionId, { enabled: on });
  const checklist = useFollowupChecklist(briefSessionId, { enabled: on });
  const needEvidence =
    checks.items.some((item) => item.in_briefing && Array.isArray(item.segment_ids) && item.segment_ids.length > 0) ||
    checklistNeedsEvidence(checklist.checklist, briefSessionId);
  const signals = useCaseSignals(detail, { enabled: on, needEvidence });
  const questions = useFollowupQuestions(signals.session?.id ?? null, { enabled: on });
  const history = useSignalHistory(caseId, { enabled: on });
  const appKey = on ? `case-child-app:${caseId}` : null;
  const childAppInfo = useRemote(appKey, () => childApp.get(caseId), '아이 앱 정보를 불러오지 못했습니다.', () => false);
  const brief = preBriefingValues({ childApp: childAppInfo.data, session, detail, signals, questions, caseId, history, checks, checklist });
  return { brief, detail, signals };
}

function useTicks(sessionId) {
  const key = sessionId ? `ispot-brief-ticks:${sessionId}` : null;
  const [ticks, setTicks] = useState(() => new Set());
  useEffect(() => {
    let saved = [];
    try {
      saved = key ? JSON.parse(window.localStorage.getItem(key) || '[]') : [];
    } catch {
      saved = [];
    }
    setTicks(new Set(Array.isArray(saved) ? saved : []));
  }, [key]);
  const toggle = (text) =>
    setTicks((prev) => {
      const next = new Set(prev);
      if (next.has(text)) next.delete(text);
      else next.add(text);
      try {
        if (key) window.localStorage.setItem(key, JSON.stringify([...next]));
      } catch {
        // 저장이 막힌 브라우저면 이 화면에서만
      }
      return next;
    });
  return { ticks, toggle };
}

function BriefBody({ caseId }) {
  const { brief, signals } = useBrief(caseId);
  const { ticks, toggle } = useTicks(signals.session?.id ?? null);
  const checks = brief.checks || [];
  const done = checks.filter((c) => ticks.has(c.text)).length;

  return (
    <>
      <p className="ma-sec-t">먼저 볼 것</p>
      {(brief.firstCards || []).map((c) => (
        <div key={c.key} className="ma-card ma-lead">
          <span className="ma-lead-tag">{c.title}</span>
          {c.q ? <span className="ma-lead-q">{c.q}</span> : null}
          {c.main ? <b className="ma-lead-main">{c.main}</b> : null}
          <span className="ma-src">{c.src || c.note}</span>
        </div>
      ))}
      <p className="ma-sec-t">
        확인할 사항 <span className="ma-note">({done}/{checks.length})</span>
      </p>
      {brief.checksNote ? <span className="ma-note">{brief.checksNote}</span> : null}
      {checks.map((c) => (
        <label key={c.key} className="ma-rq">
          <input type="checkbox" checked={ticks.has(c.text)} onChange={() => toggle(c.text)} />
          <span>
            {c.text}
            <span className="ma-src">근거 · {c.why}</span>
          </span>
        </label>
      ))}
      {brief.checksError ? <span className="ma-err">{brief.checksError}</span> : null}
      <p className="ma-sec-t">
        추가 질문{' '}
        <span className="ma-chip ma-ai" style={{ marginLeft: '4px' }}>
          AI 초안
        </span>
      </p>
      {(brief.questions || []).map((q) => (
        <div key={q.key} className="ma-rq" style={{ cursor: 'default' }}>
          <span className="ma-chip">{q.chip}</span>
          <span>"{q.text}"</span>
        </div>
      ))}
      {brief.questionNote ? <span className="ma-note">{brief.questionNote}</span> : null}
      <p className="ma-note" style={{ margin: 0 }}>
        브리핑 내용 수정과 질문 편집은 웹에서 할 수 있어요. AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
      </p>
      <Link className="ma-btn ma-btn-p ma-btn-block ma-cta" to={`/AppRecord?case=${caseId}`}>
        이 상담 녹음 시작
      </Link>
    </>
  );
}

function NoCase() {
  return (
    <>
      <div className="ma-card ma-empty" style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--mut)' }}>
        브리핑을 볼 아이를 사례 목록에서 골라 주세요
      </div>
      <Link className="ma-btn ma-btn-p ma-btn-block" to="/AppCases">
        사례 목록
      </Link>
    </>
  );
}

/** 머리: '‹ 일정 · 오늘 16:00 · 9회차' 와 '이서윤 상담 전 브리핑'. */
function useHead(caseId, userId) {
  const my = useAppCases(userId);
  const detail = useCaseDetail(caseId, { enabled: !!userId && !!caseId });
  const now = new Date();
  const sched = useAppSchedule(!!userId && !!caseId, ymd(now), ymd(addDays(now, 27)));
  const next = sched.items.find((e) => e.kind === 'CONSULT' && e.case_id === caseId);
  const row = my.rows.find((r) => r.id === caseId);
  const name = row ? childLabelOf(row) : detail.caseInfo?.alias ?? '';
  let when = '';
  if (next) {
    const d = parseYmd(next.date);
    const day = next.date === ymd(now) ? '오늘' : `${d.getMonth() + 1}/${d.getDate()}`;
    when = `${day}${next.time ? ' ' + next.time : ''}`;
  }
  const count = detail.caseInfo ? `${detail.caseInfo.sessionCount + 1}회차` : '';
  return { name, line: [when, count].filter(Boolean).join(' · ') };
}

function Head({ userId, caseId }) {
  const head = useHead(caseId, userId);
  return (
    <>
      <div className="ma-sub">
        <Link to="/AppSchedule" style={{ color: 'inherit' }}>
          ‹ 일정
        </Link>
        {head.line ? ' · ' + head.line : ''}
      </div>
      <h1>{head.name ? `${head.name} 상담 전 브리핑` : '상담 전 브리핑'}</h1>
    </>
  );
}

export default function AppBrief() {
  const [params] = useSearchParams();
  const caseId = params.get('case');
  return (
    <MobileAppShell
      cur="cal"
      screen="brief"
      head={caseId ? ({ userId }) => <Head userId={userId} caseId={caseId} /> : null}
      sub="상담 전 확인"
      title="상담 전 브리핑"
    >
      {() => (caseId ? <BriefBody caseId={caseId} /> : <NoCase />)}
    </MobileAppShell>
  );
}
