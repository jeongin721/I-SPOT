// 3 · 4단계가 함께 쓰는 작은 표시 함수(공용 파일을 고치지 않으려고 이 화면 묶음 안에 둔다).
//  - 근거(basis) 모양: API_CONTRACT 27절 '회차 통합 요약' — SEGMENT · MEASUREMENT · SESSION · PROFILE.
//  - 서버 시각은 시간대 없이 올 수 있어 counselor-web 의 parseBackendTime 으로 읽는다.
import { parseBackendTime } from '@cw/data/time';
import { DASH } from '../data/format';

const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const pad = (n) => String(n).padStart(2, '0');

export const CONSULT_LABELS = { INITIAL: '초기상담', REGULAR: '정기상담', VISIT: '방문상담', OFFICE: '내방상담', PHONE: '전화상담' };
const TIMING = { FASTING: '공복', POST_MEAL: '식후', RANDOM: '' };
const METRIC = {
  systolic: '혈압', diastolic: '혈압', pulse: '맥박', blood_glucose_fasting: '공복 혈당', blood_glucose_post_meal: '식후 혈당',
  blood_glucose_random: '혈당', weight_kg: '체중', body_temp_c: '체온',
};

export function toDate(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const [y, m, d] = String(value).split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  return parseBackendTime(String(value));
}
/** 11/13(금) */
export function mdw(value) {
  const d = toDate(value);
  return d ? `${d.getMonth() + 1}/${d.getDate()}(${DAYS[d.getDay()]})` : DASH;
}
/** 2026-11-13(금) 10:00 */
export function ymdwhm(value) {
  const d = toDate(value);
  if (!d) return DASH;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}(${DAYS[d.getDay()]}) ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export function clock(ms) {
  const s = Math.max(0, Math.floor((ms || 0) / 1000));
  return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
}
const num = (x) => (Number.isInteger(x) ? String(x) : String(Math.round(x * 10) / 10));

/** 측정 한 줄을 사람이 읽는 글로(값만, 정상 · 위험 판정 없음). */
export function measurementLine(m) {
  if (!m) return '';
  const p = [];
  if (m.systolic != null && m.diastolic != null) p.push(`혈압 ${m.systolic}/${m.diastolic}mmHg`);
  if (m.pulse != null) p.push(`맥박 ${m.pulse}회/분`);
  if (m.blood_glucose != null) p.push(`${TIMING[m.glucose_timing] ? TIMING[m.glucose_timing] + ' ' : ''}혈당 ${num(m.blood_glucose)}mg/dL`);
  if (m.weight_kg != null) p.push(`체중 ${num(m.weight_kg)}kg`);
  if (m.body_temp_c != null) p.push(`체온 ${num(m.body_temp_c)}℃`);
  (m.extra_results || []).forEach((x) => p.push(`${x.name} ${num(x.value)}${x.max_value != null ? '/' + num(x.max_value) : ''}${x.unit || ''}`));
  return p.join(' · ');
}

/**
 * 근거 목록을 짧은 글로. ctx: { segs: Map(segment_id → segment), meas: Map(id → 측정) }.
 * 발화는 '00:41 말씀', 측정은 측정일 · 항목('11/13 측정(혈압 · CIST)'), 회차는 'n회차 상담', 기본정보는 '기본정보'.
 */
export function basisText(list, ctx) {
  const out = [];
  const byMeas = new Map();
  (list || []).forEach((b) => {
    if (!b) return;
    if (b.kind === 'SEGMENT') {
      (b.segment_ids || []).forEach((id) => {
        const seg = ctx.segs && ctx.segs.get(id);
        out.push(seg ? `${clock(seg.start_ms)} 말씀` : '상담 발화');
      });
    } else if (b.kind === 'MEASUREMENT') {
      const key = b.measurement_id || '';
      const label = METRIC[b.metric] || String(b.metric || '').split(':').slice(1).join(':') || '측정';
      if (!byMeas.has(key)) {
        byMeas.set(key, []);
        out.push({ meas: key });
      }
      const arr = byMeas.get(key);
      if (!arr.includes(label)) arr.push(label);
    } else if (b.kind === 'SESSION') {
      out.push(b.session_number ? `${b.session_number}회차 상담` : '지난 상담');
    } else if (b.kind === 'PROFILE') {
      out.push('기본정보');
    }
  });
  const text = out.map((x) => {
    if (typeof x === 'string') return x;
    const m = ctx.meas && ctx.meas.get(x.meas);
    const when = m ? `${mdw(m.measured_at).replace(/\(.\)$/, '')} 측정` : '측정';
    return `${when}(${byMeas.get(x.meas).join(' · ')})`;
  });
  return [...new Set(text)].join(' · ') || DASH;
}

export function segMap(transcriptEnvelope) {
  const segs = (transcriptEnvelope && transcriptEnvelope.transcript && transcriptEnvelope.transcript.segments) || [];
  return new Map(segs.map((s) => [s.segment_id, s]));
}

export function errText(e, fallback) {
  return e && e.message ? e.message : fallback;
}

/** 이름 가려서 복사: 디자인 예시 이름 말고 이 사례의 별칭도 가린다(김순자 → 김○자). */
export function maskName(text, name) {
  if (!name || name.length < 2) return text;
  return String(text).split(name).join(name[0] + '○' + name.slice(2));
}

/** ?session= 이 없으면 이 사례의 가장 최근 회차를 쓴다. */
export async function resolveSession(listSessions, caseId, sessionId) {
  if (sessionId) return sessionId;
  const page = await listSessions(caseId, { page_size: 50 });
  const items = (page && page.items) || [];
  if (!items.length) return null;
  return items.reduce((a, b) => (b.session_number > a.session_number ? b : a)).id;
}
