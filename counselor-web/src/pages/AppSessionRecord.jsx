// 상담사 앱(폰) · 회차 상담 기록 보기(읽기 전용)
// **디자인 원본이 없는 화면**(11/19 멘토 피드백 — 폰으로 녹음한 뒤 요약 · 일지를 보려고 PC 로 가야 해서 불편하다 →
// 경진님 결정: 일단 폰에서 '볼 수' 있게, 고치기 · 승인은 나중). 카드 · 칩 · 머리(뒤로 가기)는 이전 상담(AppHistory)과
// 다음 상담 준비(AppBrief)의 모양을 그대로 따랐다. 디자이너 확인이 필요하다.
//
// 들어오는 곳: 업로드 목록의 다 올린 녹음 줄 · 이전 상담의 회차 카드 '기록 보기'. 주소 ?case=<사례 ID>&session=<회차 ID>.
// 서버 연결 — 웹이 쓰는 훅을 그대로 쓴다(서버는 고치지 않았다).
//  - 회차 상태 · 원문: useSessionDetail(GET /sessions/{id}). 원문 변환 · AI 분석 중이면 저절로 다시 본다.
//  - 상담 요약: useSummaryReview(GET /sessions/{id}/summary). 요약이 생긴 회차만 부른다. 승인한 요약은 '확정',
//    아니면 'AI 초안 · 승인 전' 칩. 개요와 사정 관점 4칸(웹 상담 요약과 같은 이름 ASSESSMENT_LABELS)을 보인다.
//  - 상담일지: useSessionDocuments(GET /sessions/{id}/documents)의 가장 최근 상담일지. 승인 전이면 '작성 중'.
// 이 화면은 아무것도 고치거나 승인하지 않는다(단추 없음). 고치기 · 승인은 웹에서 한다.
import { useLocation, useSearchParams } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { appFrom } from '../data/appReturn';
import { NOT_PROVIDED } from '../data/caseRows';
import { signedIn } from '../data/screens/common';
import { ASSESSMENT_LABELS } from '../data/screens/noteWrite';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { useSessionDocuments } from '../data/useSessionDocuments';
import { ASSESSMENT_KEYS, useSummaryReview } from '../data/useSummaryReview';

/** 회차 상태 칩 색(이전 상담과 같다): 끝남은 흐리게, 처리 중 · 확인 필요는 금색, 실패는 빨강. */
const TONE_MA = { done: 'ma-chip', progress: 'ma-chip ma-gold', action: 'ma-chip ma-gold', failed: 'ma-chip ma-red' };

/** 지금 상태에서 다음에 할 일(웹에서). 상태 이름은 칩에 있다. */
const NEXT_STEP = {
  CREATED: '녹음이 아직 올라가지 않았습니다.',
  AUDIO_UPLOADED: '원문 변환을 기다리고 있습니다.',
  STT_PROCESSING: '원문으로 바꾸는 중입니다. 끝나면 이 화면이 저절로 바뀝니다.',
  STT_REVIEW_REQUIRED: '웹에서 원문을 검수하면 AI 분석을 요청할 수 있습니다.',
  STT_CONFIRMED: '웹에서 AI 분석을 요청하면 상담 요약 초안이 만들어집니다.',
  AI_PROCESSING: 'AI 분석 중입니다. 끝나면 상담 요약 초안이 여기에 보입니다.',
  AI_REVIEW_REQUIRED: '웹에서 AI 결과와 상담 요약을 검수하고 승인합니다.',
  APPROVED: '',
  STT_FAILED: '원문 변환이 실패했습니다. 업로드 화면이나 웹에서 다시 요청할 수 있습니다.',
  AI_FAILED: 'AI 분석이 실패했습니다. 웹에서 다시 요청할 수 있습니다.',
};

/** 위 칩: 요약을 승인한 회차는 상담일지 승인 여부까지 본다. */
function overallChip(session, diary) {
  if (session.status !== 'APPROVED') return { label: session.statusLabel, cls: TONE_MA[session.tone] ?? 'ma-chip' };
  if (diary && diary.status !== 'APPROVED') return { label: '일지 승인 전', cls: 'ma-chip ma-gold' };
  if (diary) return { label: '승인됨', cls: 'ma-chip' };
  return { label: '요약 승인됨', cls: 'ma-chip' };
}

function RecordBody({ sessionId }) {
  const auth = useAuthSession();
  const on = signedIn(auth) && !!sessionId;
  const detail = useSessionDetail(sessionId, { enabled: on });
  const s = detail.session;
  const sum = useSummaryReview(sessionId, { enabled: on && !!s?.hasSummary });
  const docs = useSessionDocuments(sessionId, { enabled: on && !!s });
  const diary = docs.consultationRecord;

  if (detail.error) return <span className="ma-err">{detail.error}</span>;
  if (!s) return <span className="ma-note">불러오는 중</span>;

  const chip = overallChip(s, diary);
  const date = s.consultedDate !== NOT_PROVIDED ? s.consultedDate : `${s.createdDate} 등록`;
  const next = s.errorMessage && (s.status === 'STT_FAILED' || s.status === 'AI_FAILED') ? `${NEXT_STEP[s.status]} (${s.errorMessage})` : NEXT_STEP[s.status];
  const source = s.source === 'DOCUMENT' ? '상담 기록 문서에서 옮김' : s.transcriptConfirmed ? '원문 검수 끝' : s.hasTranscript ? '원문 검수 전' : '원문 없음';
  const sourceLine = [source, s.audio?.durationLabel && s.audio.durationLabel !== NOT_PROVIDED ? `녹음 ${s.audio.durationLabel}` : ''].filter(Boolean).join(' · ');

  const approved = sum.status === 'APPROVED';
  const f = sum.fields;
  const parts = ASSESSMENT_KEYS.map((k) => ({ k, label: ASSESSMENT_LABELS[k], text: f.assessment[k]?.trim() })).filter((p) => p.text);
  const diaryText = diary?.content?.trim() || '';

  return (
    <>
      <section className="ma-card ma-ss" aria-label="회차 상태">
        <div className="ma-ss-top">
          <b>{s.numberLabel}</b>
          <span className="ma-note">
            {date}
            {s.kindLabel !== NOT_PROVIDED ? ` · ${s.kindLabel}` : ''}
          </span>
          <span className={chip.cls} style={{ marginLeft: 'auto' }}>
            {chip.label}
          </span>
        </div>
        <span className="ma-note">{sourceLine}</span>
        {next ? <p>{next}</p> : null}
      </section>

      <p className="ma-sec-t">상담 요약</p>
      <section className="ma-card ma-ss" aria-label="상담 요약">
        {!s.hasSummary ? (
          <span className="ma-note">아직 상담 요약이 없습니다. AI 분석이 끝나면 초안이 보입니다.</span>
        ) : sum.loading && !sum.hasSummary ? (
          <span className="ma-note">불러오는 중</span>
        ) : sum.error ? (
          <span className="ma-err">{sum.error}</span>
        ) : (
          <>
            <div className="ma-ss-top">
              {approved ? (
                <span className="ma-chip">확정{sum.approvedAt ? ` · ${sum.approvedAt}` : ''}</span>
              ) : (
                <span className="ma-chip ma-ai">AI 초안 · 승인 전</span>
              )}
            </div>
            {f.overview.trim() ? <p style={{ whiteSpace: 'pre-wrap' }}>{f.overview.trim()}</p> : null}
            {parts.map((p) => (
              <div key={p.k} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="ma-ss-lb">{p.label}</span>
                <p style={{ whiteSpace: 'pre-wrap' }}>{p.text}</p>
              </div>
            ))}
            {!f.overview.trim() && parts.length === 0 ? <span className="ma-note">요약 내용이 비어 있습니다.</span> : null}
          </>
        )}
      </section>

      <p className="ma-sec-t">상담일지</p>
      <section className="ma-card ma-ss" aria-label="상담일지">
        {docs.error ? (
          <span className="ma-err">{docs.error}</span>
        ) : docs.loading && !diary ? (
          <span className="ma-note">불러오는 중</span>
        ) : !diary ? (
          <span className="ma-note">아직 상담일지가 없습니다. 상담일지는 웹에서 씁니다.</span>
        ) : (
          <>
            <div className="ma-ss-top">
              <b style={{ fontSize: '14.5px', minWidth: 0 }}>{diary.title}</b>
              <span className={diary.status === 'APPROVED' ? 'ma-chip' : 'ma-chip ma-gold'} style={{ marginLeft: 'auto' }}>
                {diary.status === 'APPROVED' ? '승인됨' : '작성 중 · 승인 전'}
              </span>
            </div>
            {diaryText ? <p style={{ whiteSpace: 'pre-wrap' }}>{diaryText}</p> : <span className="ma-note">본문이 비어 있습니다.</span>}
          </>
        )}
      </section>

      <p className="ma-note" style={{ margin: 0 }}>
        상담 요약 · 상담일지 고치기와 승인은 웹에서 할 수 있습니다. AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.
      </p>
    </>
  );
}

function Missing() {
  return (
    <div className="ma-card ma-empty" style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--mut)' }}>
      볼 회차를 업로드 목록이나 이전 상담에서 골라 주세요
    </div>
  );
}

/** 머리: '이서윤 · C-2026-0351' 와 '3회차 상담 기록'. */
function Head({ userId, caseId, sessionId }) {
  const my = useAppCases(userId);
  const detail = useSessionDetail(sessionId, { enabled: !!userId && !!sessionId, poll: false });
  const cid = detail.session?.caseId ?? caseId ?? null;
  const caseDetail = useCaseDetail(cid, { enabled: !!userId && !!cid });
  const row = my.rows.find((r) => r.id === cid);
  const name = row ? childLabelOf(row) : caseDetail.caseInfo?.alias ?? '';
  const number = row?.case_number ?? caseDetail.caseInfo?.caseNumber ?? '';
  return (
    <>
      <div className="ma-sub">{[name, number].filter(Boolean).join(' · ') || '상담 기록'}</div>
      <h1>{detail.session ? `${detail.session.numberLabel} 상담 기록` : '상담 기록'}</h1>
    </>
  );
}

export default function AppSessionRecord() {
  const [params] = useSearchParams();
  const location = useLocation();
  const caseId = params.get('case');
  const sessionId = params.get('session');
  const fallback = caseId ? `/AppHistory?case=${caseId}` : '/AppUpload';
  return (
    <MobileAppShell
      cur="cases"
      screen="rec-view"
      back={appFrom(location.state, '/AppSessionRecord') ?? fallback}
      head={sessionId ? ({ userId }) => <Head userId={userId} caseId={caseId} sessionId={sessionId} /> : null}
      sub="상담 기록"
      title="상담 기록"
    >
      {() => (sessionId ? <RecordBody sessionId={sessionId} /> : <Missing />)}
    </MobileAppShell>
  );
}
