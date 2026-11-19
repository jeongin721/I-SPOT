// 상담사 앱(폰) · 이전 상담(읽기 전용)
// 원본: 11/17 'I-SPOT 상담사 웹 화면 설계 · 각진 UI' ⑨ 의 앱 · 이전 상담(AppHistory.dc.html). 사례 목록의 사례 요약 창 '이전 상담' 에서 온다.
//
// 서버 연결: 주소 ?case=<사례 ID>. 웹 사례 상세 '상담 이력' 탭(CaseHistory)과 **같은 값**(caseHistoryValues)을 폰 모양으로 보인다.
//  - 위 카드: '총 N회 · 첫 상담일 ~ 최근 상담일'(상담 일시를 넣은 회차만).
//    흐름 줄 값은 승인한 최근 회차들의 상담 요약(useApprovedSummaries)이다. 칩은 디자인 그대로 'AI 분석 · N~M회차'
//    (11/17 결정 '디자인 그대로' — 웹의 '승인된 회차 요약 모음 · AI 생성 아님' 칩과 다르다).
//    주제 비중은 회차 분석의 대화 주제를 더한 것(AI 제안)이라 웹과 같은 안내(topicNote)를 붙인다.
//  - 회차 선택: 회차 목록(useCaseDetail)에서 고르면 그 회차 카드가 보인다. 카드 내용은 고른 회차만 부른다.
//      · 요약: GET /sessions/{id}/summary 의 overview. 승인했으면 '상담 요약', 아니면 'AI 요약 (웹에서 확정 전)'(디자인 문구).
//      · 상담 일지: 그 회차 문서 중 마지막 상담일지(GET /sessions/{id}/documents). 승인 전이면 '(작성 중)'.
//      · 주요 발화: 요약 근거 발화(summary_evidence) 중 앞의 3개를 원문에서 찾아 '시각 · 화자 "말"'(근거가 있을 때만 원문을 부른다).
//      · 신호: 신호 이력의 세부 신호(AI 제안, 화자 확인 중이면 '보류'). 머리글 없이 칩만(디자인 그대로).
//  - '기록 보기': 그 회차의 상담 기록 화면(AppSessionRecord — 요약 사정 관점 4칸 · 일지 전문, 읽기 전용, 11/19).
//  - 11/19 디자인: 회차 선택 목록이 아래 창이 아니라 버튼 아래로 펼쳐진다(아래 공간이 모자라면 위로, 목록 안 스크롤).
//    회차를 고르면 그 회차 카드가 올라온다(동작 줄이기면 움직이지 않음).
// 고치기는 웹에서 한다. 이 화면은 폰에 아무것도 저장하지 않는다.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { closeWithAnim, staggerIn } from '../components/MobileAppShellMotion';
import { documents as documentsApi, summary as summaryApi, transcript as transcriptApi } from '../api/endpoints';
import { DOC_TYPE_CONSULTATION_RECORD } from '../api/types';
import { appFrom } from '../data/appReturn';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSignalHistory } from '../data/useSignalHistory';
import { useApprovedSummaries } from '../data/useApprovedSummaries';
import { caseHistoryValues } from '../data/screens/caseDetail';
import { signedIn } from '../data/screens/common';
import { TYPE_SHORT } from '../data/signalHistoryRows';
import { SPEAKER_LABELS } from '../data/transcriptRows';
import { NOT_PROVIDED } from '../data/caseRows';
import { formatClock } from '../data/time';
import { useRemote } from '../data/useRemote';
import { childLabelOf, useAppCases } from '../data/useAppCases';

/** 회차 상태 칩: 확정(끝남)은 흐리게, 처리 중 · 확인 필요는 금색, 실패는 빨강(디자인 '확정' chip · '처리 중' chip gold). */
const TONE_MA = { done: 'ma-chip', progress: 'ma-chip ma-gold', action: 'ma-chip ma-gold', failed: 'ma-chip ma-red' };
/** 주요 발화로 보일 근거 발화 수. */
const LINES_N = 3;

const mmdd = (date) => {
  const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(date || '');
  return m ? `${m[1]}/${m[2]}` : '';
};

/** 고른 회차 카드. 그 회차의 요약 · 상담일지 · 근거 발화를 부른다. */
function SessionCard({ row, historyRow }) {
  const id = row.id;
  const sum = useRemote(`app-hist-sum:${id}`, () => summaryApi.get(id), '요약을 불러오지 못했습니다.');
  const docs = useRemote(`app-hist-docs:${id}`, () => documentsApi.list(id), '상담일지를 불러오지 못했습니다.');
  const evidenceIds = useMemo(() => {
    const ids = [];
    for (const item of sum.data?.summary_evidence ?? []) {
      for (const segmentId of item.segment_ids ?? []) if (!ids.includes(segmentId)) ids.push(segmentId);
    }
    return ids.slice(0, LINES_N);
  }, [sum.data]);
  const tr = useRemote(evidenceIds.length > 0 ? id : null, () => transcriptApi.get(id), '원문을 불러오지 못했습니다.');

  const summary = sum.data?.summary ?? null;
  const sumLb = summary?.status === 'APPROVED' ? '상담 요약' : 'AI 요약 (웹에서 확정 전)';
  let sumText = summary?.overview?.trim() || '';
  if (!sumText) sumText = sum.loading ? '불러오는 중' : sum.error || '아직 요약이 없습니다.';

  const records = (docs.data ?? []).filter((d) => d.doc_type === DOC_TYPE_CONSULTATION_RECORD);
  const diary = records.length > 0 ? records[records.length - 1] : null;
  const diaryText = diary?.content?.trim() || '';

  const segments = new Map((tr.data?.transcript?.segments ?? []).map((s) => [s.segment_id, s]));
  const lines = evidenceIds.map((sid) => segments.get(sid)).filter(Boolean);

  const sigs = (historyRow?.subtypes ?? []).map(
    (s) => `${TYPE_SHORT[s.abuse_type] ?? s.abuse_type} · ${s.subtype}${s.pending ? ' · 보류' : ''}`,
  );

  return (
    <article className="ma-card ma-ss" aria-label={`${row.numberLabel} 상담 내역`}>
      <div className="ma-ss-top">
        <b>{row.numberLabel}</b>
        <span className="ma-note">
          {row.date} · {row.kindLabel}
        </span>
        <span className={TONE_MA[row.tone] ?? 'ma-chip'} style={{ marginLeft: 'auto' }}>
          {row.statusLabel}
        </span>
      </div>
      <span className="ma-ss-lb">{summary ? sumLb : '요약'}</span>
      <p>{sumText}</p>
      {diaryText ? (
        <>
          <span className="ma-ss-lb">상담 일지{diary.status === 'APPROVED' ? '' : ' (작성 중)'}</span>
          <p style={{ whiteSpace: 'pre-wrap' }}>{diaryText}</p>
        </>
      ) : null}
      {docs.error ? <span className="ma-note">{docs.error}</span> : null}
      {lines.length > 0 ? (
        <div className="ma-ss-q">
          <span className="ma-ss-lb">주요 발화</span>
          {lines.map((s) => (
            <span key={s.segment_id}>
              <small>
                {formatClock(s.start_ms)} · {SPEAKER_LABELS[s.speaker] ?? s.speaker}
              </small>
              "{s.text}"
            </span>
          ))}
        </div>
      ) : null}
      {tr.error ? <span className="ma-note">{tr.error}</span> : null}
      {sigs.length > 0 ? (
        <div className="ma-ss-sig">
          {sigs.map((g) => (
            <span key={g} className="ma-chip ma-gold">
              {g}
            </span>
          ))}
        </div>
      ) : null}
      <Link
        className="ma-btn ma-btn-sm"
        to={`/AppSessionRecord?case=${row.caseId}&session=${id}`}
        state={{ from: `/AppHistory?case=${row.caseId}` }}
      >
        기록 보기
      </Link>
    </article>
  );
}

function HistoryBody({ caseId }) {
  const session = useAuthSession();
  const on = signedIn(session) && !!caseId;
  const detail = useCaseDetail(caseId, { enabled: on });
  const history = useSignalHistory(caseId, { enabled: on });
  const approved = useApprovedSummaries(history.sessions, { enabled: on });
  const v = caseHistoryValues({ session, detail, history, approved, caseId });
  const [pick, setPick] = useState(null);
  const [pkOpen, setPkOpen] = useState(false);
  // 펼친 목록의 방향(위로 펼침)과 높이(디자인 pkUp · pkMax).
  const [pkUp, setPkUp] = useState(false);
  const [pkMax, setPkMax] = useState(300);
  const btnRef = useRef(null);
  const dropRef = useRef(null);
  const firstPick = useRef(true);

  // 회차를 고르면 그 회차 카드를 올린다(디자인 CH.pick).
  useEffect(() => {
    if (firstPick.current) {
      firstPick.current = false;
      return;
    }
    staggerIn('.ma-amain .ma-ss');
  }, [pick]);

  const rows = detail.sessions.map((row) => ({
    ...row,
    date: row.consultedDate !== NOT_PROVIDED ? row.consultedDate : `${row.createdDate} 등록`,
  }));
  const dated = detail.sessions.map((row) => row.consultedDate).filter((d) => d !== NOT_PROVIDED).sort();
  const total = detail.sessionTotal ?? rows.length;
  const range =
    `총 ${total}회` + (dated.length > 0 ? ` · ${mmdd(dated[0])} ~ ${mmdd(dated[dated.length - 1])}` : '');
  const nums = (approved.items ?? []).map((item) => item.sessionNumber);
  const apRange = nums.length === 0 ? '' : nums.length === 1 ? `${nums[0]}회차` : `${nums[0]}~${nums[nums.length - 1]}회차`;
  const flow = (v.periods || []).map((p) => {
    const [no, date] = p.range.split(' · ');
    return { k: no, t: p.title, d: p.note || date || '' };
  });
  const cur = rows.find((r) => r.id === pick) ?? null;
  const historyRow = cur ? history.sessions.find((h) => h.session_id === cur.id) : null;

  if (detail.error) return <span className="ma-err">{detail.error}</span>;

  const pkClose = (then) =>
    closeWithAnim(dropRef.current, () => {
      setPkOpen(false);
      if (then) then();
    });
  // 버튼 아래 공간(아래 메뉴 위까지)이 모자라면 위(머리 아래까지)로 펼친다. 높이는 회차 수만큼, 최대 300px(디자인 값).
  const pkOpenFn = () => {
    if (pkOpen) {
      pkClose();
      return;
    }
    let up = false;
    let mx = 300;
    try {
      const b = btnRef.current.getBoundingClientRect();
      const tb = document.querySelector('.ma-tabs');
      const hd = document.querySelector('.ma-ahd');
      const bottomEdge = tb ? tb.getBoundingClientRect().top : window.innerHeight;
      const topEdge = hd ? hd.getBoundingClientRect().bottom : 0;
      const below = bottomEdge - b.bottom - 14;
      const above = b.top - topEdge - 14;
      const want = Math.min(300, rows.length * 58 + 16);
      if (below >= Math.min(want, 180)) mx = Math.min(want, below);
      else if (above > below) {
        up = true;
        mx = Math.min(want, above);
      } else mx = Math.max(below, 120);
    } catch {
      // 자리를 못 재면 아래로 300px
    }
    setPkUp(up);
    setPkMax(Math.max(120, Math.round(mx)));
    setPkOpen(true);
  };

  return (
    <>
      <section className="ma-card ma-hs-sum" aria-label="이전 상담 요약">
        <div className="ma-hs-top">
          <b>{detail.loading && !detail.caseInfo ? '불러오는 중' : range}</b>
          {apRange ? <span className="ma-chip ma-ai">AI 분석 · {apRange}</span> : null}
        </div>
        {flow.length > 0 ? (
          <div className="ma-hs-flow">
            {flow.map((f) => (
              <div key={f.k} className="ma-hs-fl">
                <small>{f.k}</small>
                <span>
                  {f.t}
                  <i>{f.d}</i>
                </span>
              </div>
            ))}
          </div>
        ) : null}
        {v.overviewNote ? <span className="ma-note">{v.overviewNote}</span> : null}
        {(v.topics || []).length > 0 || v.topicNote ? (
          <div className="ma-hs-bars" aria-label="주제 비중">
            <span className="ma-ss-lb">주제 비중</span>
            {(v.topics || []).map((b) => (
              <div key={b.label} className="ma-hs-bar">
                <span>{b.label}</span>
                <span className="ma-tr">
                  <i style={{ width: b.width }}></i>
                </span>
                <b>{b.pct}</b>
              </div>
            ))}
            {v.topicNote ? <span className="ma-note">{v.topicNote}</span> : null}
          </div>
        ) : null}
      </section>
      <p className="ma-sec-t">회차별 상담 내역 · {total}회</p>
      {v.sessionsNote ? <span className="ma-note">{v.sessionsNote}</span> : null}
      {rows.length > 0 ? (
        <div className="ma-pk-wrap">
          <button
            type="button"
            ref={btnRef}
            className={'ma-card ma-pk-btn' + (pkOpen ? ' ma-open' : '')}
            aria-haspopup="listbox"
            aria-expanded={pkOpen ? 'true' : 'false'}
            onClick={pkOpenFn}
          >
            <span className="ma-pk-l">{cur ? cur.numberLabel : '회차 선택'}</span>
            <span className="ma-pk-s">{cur ? `${cur.date} · ${cur.kindLabel}` : ''}</span>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>
          </button>
          {pkOpen && (
            <>
              <div className="ma-pk-catch" onClick={() => pkClose()}></div>
              <div ref={dropRef} className={'ma-pk-drop' + (pkUp ? ' ma-up' : '')} style={{ maxHeight: pkMax + 'px' }} role="listbox" aria-label="회차 목록">
                {rows.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className={'ma-pk-it' + (r.id === pick ? ' ma-on' : '')}
                    role="option"
                    aria-selected={r.id === pick ? 'true' : 'false'}
                    onClick={() => pkClose(() => setPick(r.id))}
                  >
                    <b>{r.numberLabel}</b>
                    <span className="ma-note">
                      {r.date} · {r.kindLabel}
                    </span>
                    <span className={TONE_MA[r.tone] ?? 'ma-chip'} style={{ marginLeft: 'auto' }}>
                      {r.statusLabel}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      ) : null}
      {cur ? <SessionCard key={cur.id} row={cur} historyRow={historyRow} /> : null}
    </>
  );
}

function NoCase() {
  return (
    <div className="ma-card ma-empty" style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--mut)' }}>
      이전 상담을 볼 아이를 사례 목록에서 고르십시오
    </div>
  );
}

/** 머리: '이서윤 · C-2026-0351' 와 '이전 상담'. */
function Head({ userId, caseId }) {
  const my = useAppCases(userId);
  const detail = useCaseDetail(caseId, { enabled: !!userId && !!caseId });
  const row = my.rows.find((r) => r.id === caseId);
  const name = row ? childLabelOf(row) : detail.caseInfo?.alias ?? '';
  const number = row?.case_number ?? detail.caseInfo?.caseNumber ?? '';
  return (
    <>
      <div className="ma-sub">{[name, number].filter(Boolean).join(' · ')}</div>
      <h1>이전 상담</h1>
    </>
  );
}

export default function AppHistory() {
  const [params] = useSearchParams();
  const location = useLocation();
  const caseId = params.get('case');
  return (
    <MobileAppShell
      cur="cases"
      screen="hist"
      back={appFrom(location.state, '/AppHistory') ?? '/AppCases'}
      head={caseId ? ({ userId }) => <Head userId={userId} caseId={caseId} /> : null}
      sub="사례 목록"
      title="이전 상담"
    >
      {() => (caseId ? <HistoryBody caseId={caseId} /> : <NoCase />)}
    </MobileAppShell>
  );
}
