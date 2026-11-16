// 사례 상세 묶음(CaseInfo · CaseHistory · SessionDetail)이 같이 쓰는 작은 변환들. 공용 파일(src/data)은 고치지 않기로 해 여기 둔다.
import { CONSULTATION_TYPE_LABELS, SCHEDULE_CONSULT_LABELS } from '@cw/api/types';
import { href } from '../data/nav';
import { DASH, age, genderLabel, md, dayName } from '../data/format';
import { LIVING_LABELS } from '../api/senior';

/** 회차 상태 → 칩(글자 · 색). 판정 말은 쓰지 않고 처리 단계만 적는다. */
const STATUS = {
  CREATED: ['녹음 전', 'chip c-check'],
  AUDIO_UPLOADED: ['변환 대기', 'chip c-check'],
  STT_PROCESSING: ['변환 중', 'chip c-check'],
  STT_REVIEW_REQUIRED: ['검수 대기', 'chip c-check'],
  STT_CONFIRMED: ['분석 대기', 'chip c-check'],
  AI_PROCESSING: ['분석 중', 'chip c-check'],
  AI_REVIEW_REQUIRED: ['요약 검토 대기', 'chip c-check'],
  APPROVED: ['확정', 'chip c-ok'],
  STT_FAILED: ['변환 실패', 'chip c-check'],
  AI_FAILED: ['분석 실패', 'chip c-check'],
};
export function statusChip(status) {
  return STATUS[status] || [DASH, 'chip c-normal'];
}

export function kindLabel(t) {
  return (t && CONSULTATION_TYPE_LABELS[t]) || DASH;
}

/**
 * 회차가 4단계 중 어디 있는지. 0 = 녹음 전, 1~4 = 그 단계를 하는 중, 5 = 다 끝남.
 * 2단계(생활 · 정서 영역 변화)는 상담사가 영역을 확정했는지, 4단계(다음 상담 준비)는 이 회차에서 확인사항을 저장했는지로 본다.
 */
export function stepOf(session, { domainsConfirmed = false, checksSaved = false } = {}) {
  if (!session) return 0;
  switch (session.status) {
    case 'CREATED':
      return 0;
    case 'AUDIO_UPLOADED':
    case 'STT_PROCESSING':
    case 'STT_REVIEW_REQUIRED':
    case 'STT_FAILED':
      return 1;
    case 'STT_CONFIRMED':
    case 'AI_PROCESSING':
    case 'AI_FAILED':
      return 2;
    case 'AI_REVIEW_REQUIRED':
      return domainsConfirmed ? 3 : 2;
    case 'APPROVED':
      return checksSaved ? 5 : 4;
    default:
      return 1;
  }
}

export const STEP_PAGES = ['Step1Record', 'Step2Signals', 'Step3Summary', 'Step4Next'];

/** 단계 동그라미 모양(디자인의 끝남 · 지금 · 남음 세 가지 그대로). */
export function stepLook(i, cur) {
  if (i < cur) return 'done';
  if (i === cur) return 'cur';
  return 'todo';
}

/** 다음 방문(senior-brief next_visit · 일정) → '오늘 16:00' / '11/23(월) 14:00'. */
export function visitWhen(date, time) {
  if (!date) return DASH;
  const d = new Date(`${date}T00:00:00`);
  const t0 = new Date();
  t0.setHours(0, 0, 0, 0);
  const diff = Math.round((d - t0) / 86400000);
  const day = diff === 0 ? '오늘' : diff === 1 ? '내일' : `${md(d)}(${dayName(d)})`;
  return time ? `${day} ${time}` : day;
}
export function visitType(t) {
  return (t && SCHEDULE_CONSULT_LABELS[t]) || '상담';
}

/** 머리 줄: '만 82세 · 여 · 독거' */
export function subLine(c, profile) {
  const a = c ? age(c.child_birth_year) : null;
  const parts = [a !== null ? `만 ${a}세` : DASH, c ? genderLabel(c.child_gender) : DASH];
  const liv = profile && profile.living_arrangement ? LIVING_LABELS[profile.living_arrangement] : DASH;
  parts.push(liv);
  return parts.join(' · ');
}

/** 측정 한 번 → '혈압 146/86mmHg · 맥박 74회/분 · …' */
export function measureText(m) {
  if (!m) return '';
  const out = [];
  if (m.systolic != null || m.diastolic != null) out.push(`혈압 ${m.systolic ?? DASH}/${m.diastolic ?? DASH}mmHg`);
  if (m.pulse != null) out.push(`맥박 ${m.pulse}회/분`);
  if (m.blood_glucose != null) {
    const t = { FASTING: '공복 ', POST_MEAL: '식후 ', RANDOM: '' }[m.glucose_timing] ?? '';
    out.push(`${t}혈당 ${m.blood_glucose}mg/dL`);
  }
  if (m.weight_kg != null) out.push(`체중 ${m.weight_kg}kg`);
  if (m.body_temp_c != null) out.push(`체온 ${m.body_temp_c}℃`);
  (m.extra_results || []).forEach((x) => out.push(`${x.name} ${x.value}${x.max_value ? `/${x.max_value}` : x.unit || ''}`));
  return out.join(' · ');
}

/** 사례 묶음 탭 · 단계 링크. */
export function caseLinks(caseId, sessionId) {
  return {
    infoHref: href('CaseInfo', { caseId }),
    historyHref: href('CaseHistory', { caseId }),
    uploadHref: href('Upload', { caseId }),
    goUpload: () => {
      window.location.hash = href('Upload', { caseId }).slice(1);
    },
    stepHrefs: STEP_PAGES.map((p) => href(p, { caseId, sessionId })),
  };
}
