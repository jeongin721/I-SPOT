// 3단계 상담일지 작성 — 디자인 Step3Summary.dc.html. 회차 통합 요약(측정 + 상담)을 읽고 · 고치고 · 승인한다.
//  - 요약: GET · PATCH /sessions/{id}/summary, 승인 POST …/approve(승인된 요약을 고치면 …/reopen 뒤 고쳐 다시 승인).
//    '저장 · 다음 상담 준비' 가 바꾼 칸 저장 + 승인을 하고 4단계로 간다. 승인은 담당자가 이 단추를 눌렀을 때만(자동 승인 없음).
//  - '상담 요약' 칸: 통합 요약(overview) · 핵심 내용(key_points, 근거는 result.senior.key_point_basis) · 이번 측정(이 회차에 단 측정, 읽기만).
//  - 상담일지 서식: 사례번호 · 회차 · 어르신(별칭 · 성별 · 나이 · 가구형태) · 상담일시 · 장소 · 방식 · 담당 상담사(로그인한 사람)는 서버 값.
//    주요 내용(어르신 말씀) = 핵심 내용 근거 발화 원문(읽기만). 정서 상태 = 생활 · 정서 영역의 '정서'(확정 기록, 없으면 초안, 읽기만).
//    개입 내용 칸 = 요약의 상담사 메모(counselor_note, 저장됨).
//    서버에 없는 칸: 참석자 · 연계 · 다음 계획은 '—'. 생활환경 칸 · 정서 · 건강 특성 · 가족 · 생활 상황 고르기는 화면에서만(저장 안 함).
import { useEffect, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/Step3Summary.logic';
import { cases, sessions, summary as summaryApi, analysis as analysisApi, transcript as transcriptApi } from '@cw/api/endpoints';
import { senior, LIVING_LABELS, CHANGE_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href, carry } from '../data/nav';
import { DASH, age, genderLabel } from '../data/format';
import {
  CONSULT_LABELS, mdw, ymdwhm, clock, measurementLine, basisText, segMap, errText, maskName, resolveSession,
} from './Step3Summary.basis';
import View from './Step3Summary.view';

// 디자인 예시의 AI 선택(우울감 · 수면 문제 · 배우자 사별 등)이 미리 켜져 보이지 않게 모두 끈 채로 시작한다(서버에 칸 없음).
const OFF = (keys) => Object.fromEntries(keys.map((k) => [k, false]));

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = {
      ...this.state,
      tr: OFF(['우울감', '수면 문제', '식사 거름 · 식욕 저하']),
      hm: OFF(['배우자 사별', '독거']),
      draft: null, // { overview, keyPoints[], note } — 고친 것이 있을 때만
      saving: false,
      err: '',
    };
  }

  nmMask(t) {
    return maskName(super.nmMask(t), this.props.alias);
  }

  fields(sum) {
    if (this.state.draft) return this.state.draft;
    return sum ? { overview: sum.overview || '', keyPoints: sum.key_points || [], note: sum.counselor_note || '' } : null;
  }

  edit(sum, change) {
    const cur = this.fields(sum);
    if (!cur) return;
    this.setState({ draft: change({ ...cur, keyPoints: cur.keyPoints.slice() }), err: '' });
  }

  async save(sum) {
    const { sid, sessData, nextHref } = this.props;
    if (this.state.saving) return;
    if (!sum) {
      this.setState({ err: '아직 회차 요약이 없어요. 1단계에서 녹취 확인 · 분석을 먼저 해 주세요.' });
      return;
    }
    const d = this.state.draft;
    const body = {};
    if (d) {
      if (d.overview !== (sum.overview || '')) body.overview = d.overview;
      const kp = d.keyPoints.map((x) => x.trim()).filter(Boolean);
      if (kp.join('\n') !== (sum.key_points || []).join('\n')) body.key_points = kp;
      if (d.note !== (sum.counselor_note || '')) body.counselor_note = d.note;
    }
    const dirty = Object.keys(body).length > 0;
    this.setState({ saving: true, err: '' });
    try {
      if (sum.status === 'APPROVED' && dirty) await summaryApi.reopen(sid);
      if (dirty) await summaryApi.update(sid, body);
      if (sum.status !== 'APPROVED' || dirty) await summaryApi.approve(sid);
      this.setState({ saving: false, draft: null });
      window.location.hash = nextHref.slice(1);
    } catch (e) {
      // 고친 칸은 남겨 두고 서버 상태만 다시 받는다(다른 창에서 승인 · 재분석했을 수 있음).
      this.setState({ saving: false, err: errText(e, '요약을 저장 · 승인하지 못했어요. 잠시 뒤 다시 해 주세요.') });
      sessData.reload();
    }
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { shell, caseId, sid, caseData, sessData, nextHref } = this.props;
    const cd = caseData.data || {};
    const sd = sessData.data || {};
    const c = cd.c;
    const ses = sd.session;
    const sum = sd.sum ? sd.sum.summary : null;
    const result = sd.ana && sd.ana.analysis ? sd.ana.analysis.result : null;
    const sen = result ? result.senior : null;
    const warnings = (result && result.warnings) || [];
    const segs = segMap(sd.tr);
    const measList = cd.meas || [];
    const ctx = { segs, meas: new Map(measList.map((m) => [m.id, m])) };
    const visit = measList.filter((m) => m.session_id && m.session_id === sid);
    const f = this.fields(sum);
    const kpBasis = (sen && sen.key_point_basis) || [];

    // 상담 요약 칸: 통합 요약 · 핵심 내용(근거) · 이번 측정
    const sums = [];
    if (f) {
      sums.push({ k: '통합 요약', v: f.overview, set: (e) => { const t = e.target.value; this.edit(sum, (x) => ({ ...x, overview: t })); } });
      f.keyPoints.forEach((p, i) => {
        // key_point_basis[i] 는 서버 key_points[i] 의 근거 — 담당자가 고쳐도 같은 자리의 근거를 보인다.
        const b = i < (sum.key_points || []).length ? basisText(kpBasis[i], ctx) : DASH;
        sums.push({ k: `핵심 내용 ${i + 1} · 근거: ${b}`, v: p, set: (e) => { const t = e.target.value; this.edit(sum, (x) => { x.keyPoints[i] = t; return x; }); } });
      });
    } else {
      sums.push({ k: '통합 요약', v: sessData.loading ? '' : DASH, ro: true });
    }
    sums.push({ k: '이번 측정', v: visit.length ? visit.map((m) => `${mdw(m.measured_at)} ${measurementLine(m)}`).join('\n') : DASH, ro: true });

    // 주요 내용(어르신 말씀): 핵심 내용 근거 발화 원문
    const seen = new Set();
    const quotes = [];
    kpBasis.forEach((list) => (list || []).forEach((b) => {
      if (b && b.kind === 'SEGMENT') (b.segment_ids || []).forEach((id) => {
        const s = segs.get(id);
        if (s && !seen.has(id)) { seen.add(id); quotes.push(`· ${clock(s.start_ms)} "${s.text}"`); }
      });
    }));

    // 정서 상태: 생활 · 정서 영역 '정서'(확정 기록, 없으면 초안)
    const mood = sd.dom && (sd.dom.domains || []).find((d) => d.domain === 'MOOD');
    let moodText = DASH;
    if (mood && mood.saved) moodText = mood.saved.change === 'NOT_MENTIONED' ? CHANGE_LABELS.NOT_MENTIONED : `${mood.saved.text || ''}${mood.saved.change_note ? ` (${mood.saved.change_note})` : ''}`;
    else if (mood && mood.draft && mood.draft.text) moodText = `초안: ${mood.draft.text}`;

    const alias = c ? c.child_alias : DASH;
    const nLabel = ses ? `${ses.session_number}회차` : DASH;
    const typeLabel = ses && ses.consultation_type ? CONSULT_LABELS[ses.consultation_type] || DASH : DASH;
    const a = c ? age(c.child_birth_year) : null;
    const living = cd.profile && cd.profile.living_arrangement ? LIVING_LABELS[cd.profile.living_arrangement] : DASH;
    const ids = { caseId, sessionId: sid };

    let msg = this.state.err;
    if (!msg && caseData.error) msg = errText(caseData.error, '사례를 불러오지 못했어요.');
    if (!msg && sessData.error) msg = errText(sessData.error, '회차를 불러오지 못했어요.');
    if (!msg && caseData.data && !sid) msg = '이 사례에는 아직 회차가 없어요.';
    if (!msg && ses && !sum) msg = '아직 회차 요약이 없어요. 1단계에서 녹취 확인 · 분석을 먼저 해 주세요.';
    if (!msg && warnings.length) msg = warnings.join(' ');

    return {
      ...base, ...shell, sums,
      sumChip: sum && sum.status === 'APPROVED' ? '승인됨' : 'AI 초안',
      caseHref: href('CaseInfo', { caseId }), historyHref: href('CaseHistory', { caseId }), sessionHref: href('SessionDetail', ids),
      step1Href: carry('#/Step1Record', ids), step2Href: carry('#/Step2Signals', ids), step3Href: carry('#/Step3Summary', ids), step4Href: nextHref,
      crumbCase: c ? `${alias} ${c.case_number}` : DASH, crumbSession: nLabel,
      sub: ses ? `${mdw(ses.consulted_at || ses.created_at)} ${typeLabel}` : DASH,
      title: `${nLabel} 처리 · ${alias}`,
      fNo: c ? `${c.case_number} · ${nLabel}` : DASH,
      fWho: c ? `${alias} (${genderLabel(c.child_gender)}, ${a !== null ? `만 ${a}세` : DASH} · ${living})` : DASH,
      fWhen: ses ? ymdwhm(ses.consulted_at) : DASH,
      fWhere: ses ? `${ses.location || DASH} · ${typeLabel}` : DASH,
      fAttend: DASH,
      fCounselor: shell.meName || DASH,
      quotes: quotes.length ? quotes.join('\n') : DASH,
      mood: moodText,
      note: f ? f.note : '',
      noteRo: !f,
      setNote: (e) => { const t = e.target.value; this.edit(sum, (x) => ({ ...x, note: t })); },
      plan: DASH,
      msg,
      saveLabel: this.state.saving ? '저장 중…' : '저장 · 다음 상담 준비 →',
      save: (e) => { if (e && e.preventDefault) e.preventDefault(); this.save(sum); },
    };
  }
}

export default function Step3Summary(props) {
  const shell = useShell();
  const { caseId, sessionId } = useIds();
  const [sid, setSid] = useState(sessionId);
  useEffect(() => setSid(sessionId), [sessionId]);
  const caseData = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, meas, resolved] = await Promise.all([
      cases.get(caseId),
      senior.profile(caseId).catch(() => null),
      senior.measurements(caseId).catch(() => []),
      resolveSession(cases.listSessions, caseId, sessionId),
    ]);
    setSid(resolved);
    return { c, profile, meas };
  }, [shell.ready, caseId, sessionId]);
  const sessData = useAsync(async () => {
    if (!shell.ready || !sid) return null;
    const [session, sum, ana, tr, dom] = await Promise.all([
      sessions.get(sid),
      summaryApi.get(sid),
      analysisApi.get(sid).catch(() => null),
      transcriptApi.get(sid).catch(() => null),
      senior.sessionDomains(sid).catch(() => null),
    ]);
    return { session, sum, ana, tr, dom };
  }, [shell.ready, sid]);
  const alias = caseData.data && caseData.data.c ? caseData.data.c.child_alias : '';
  const nextHref = href('Step4Next', { caseId, sessionId: sid });
  const v = useDC(Logic, { ...props, shell, caseId, sid, caseData, sessData, alias, nextHref });
  return <View v={v} />;
}
