// 4단계 다음 상담 준비 — 디자인 Step4Next.dc.html.
//  - '다음 상담 전 확인할 사항' = 이 회차 분석의 확인사항 초안(result.senior.next_check_drafts) + 이 회차에서 저장한 확인 · 조치사항(next-checks).
//    초안: 체크 = 두기, '수정' = 고치기, × = 지우기. 처음엔 꺼 둔다(담당자가 골라야 저장, AI 는 보조).
//    저장한 것: '수정' 은 PATCH, × 또는 체크 해제는 저장할 때 DELETE.
//    처리 완료 단추에서 한 번에 저장 — 새로 둘 것은 POST /cases/{id}/next-checks(origin: 초안은 분석 source(AI · RULE),
//    직접 쓴 것은 COUNSELOR, edited = 초안 글을 고쳤는가 — API_CONTRACT 27절).
//    이 회차에서 초안을 한 번 저장했으면(origin AI · RULE 이 하나라도 있으면) 초안은 다시 보이지 않는다.
//  - kind(확인 CHECK · 조치 ACTION) · 기한(due_date)은 '수정' 중에 고른다(디자인에 칸이 없어 수정 칸 아래 한 줄을 더함).
//  - 재방문 일정(POST followup-visits) · 돌봄 상태(PUT care-status)는 디자인에 자리가 없어 카드 하나를 더했다(기존 클래스만 씀).
//  - '추가 질문' 카드(2026-11-17): '다음 상담에서 직접' 탭 = 이 회차 분석의 추가 질문 초안(result.followup_questions — 열린 질문 · 질문 은행)
//    + 이미 승인해 둔 질문(GET /sessions/{id}/followup-questions) + 직접 쓴 질문. 단추(디자인 문구 '발송 예약')로 고르고 '수정' 으로 고친다.
//    처리 완료 때 고른 질문 전체를 PUT(18절, 목록 통째로 바꿈) — 바뀐 게 없으면 부르지 않는다. 승인한 것만 저장된다(AI 는 초안).
//    '안부 앱으로 먼저' 탭은 고령자 안부 앱이 없어 '준비 중' 한 줄로 둔다.
import { useEffect, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/Step4Next.logic';
import { cases, sessions, analysis as analysisApi, transcript as transcriptApi, followupQuestions } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href, carry } from '../data/nav';
import { DASH } from '../data/format';
import { CONSULT_LABELS, mdw, basisText, segMap, errText, resolveSession } from './Step3Summary.basis';
import View from './Step4Next.view';

const KIND_LABELS = { CHECK: '확인할 것', ACTION: '할 조치' };
const FU_TYPES = [['VISIT', '방문'], ['PHONE', '전화'], ['REGULAR', '재상담']];
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = {
      ...this.state,
      dr: {}, // 초안 i → { on, text, kind, due, del }
      sv: {}, // 저장한 확인사항 id → { text, kind, due, del }
      adds: [], // 새로 쓴 것 [{ text, kind, due }]
      editing: false,
      eText: {}, // 수정 중 글(key → text)
      saving: false,
      err: '',
      fu: { type: 'VISIT', date: '', time: '', place: '', busy: false, done: '' },
      cs: { value: '', note: '', busy: false, done: '' },
    };
  }

  patch(key, id, change) {
    this.setState({ [key]: { ...this.state[key], [id]: { ...(this.state[key][id] || {}), ...change } }, err: '' });
  }

  rows() {
    const { data, sid } = this.props;
    const d = data.data || {};
    const saved = (d.checks || []).filter((x) => x.source_session_id && x.source_session_id === sid);
    const result = d.ana && d.ana.analysis ? d.ana.analysis.result : null;
    const sen = result ? result.senior : null;
    const draftsDone = saved.some((x) => x.origin === 'AI' || x.origin === 'RULE');
    const savedTexts = new Set(saved.map((x) => x.text));
    const drafts = draftsDone || !sen ? [] : (sen.next_check_drafts || []).map((x, i) => ({ ...x, i })).filter((x) => !savedTexts.has(x.text));
    return { saved, drafts, source: sen && sen.source === 'AI' ? 'AI' : 'RULE' };
  }

  /** 추가 질문 줄(다음 상담에서 직접). key: 저장한 것 s0.., 초안 d0.., 직접 쓴 것 x0.. */
  qRows() {
    const { data } = this.props;
    const d = data.data || {};
    const saved = (d.fq && d.fq.questions) || [];
    const result = d.ana && d.ana.analysis ? d.ana.analysis.result : null;
    const savedTexts = new Set(saved.map((q) => q.text));
    const rows = saved.map((q, i) => ({ key: 's' + i, text: q.text, kind: q.kind, source: q.source, segment_ids: q.segment_ids || [], bank_code: q.bank_code, reason: '', okDefault: true, origin: q.source === 'COUNSELOR' ? 'COUNSELOR' : 'AI' }));
    ((result && result.followup_questions) || []).forEach((q, i) => {
      if (!q || !q.text || savedTexts.has(q.text)) return;
      rows.push({ key: 'd' + i, text: q.text, kind: q.kind || 'OPEN', source: 'AI', segment_ids: q.segment_ids || [], bank_code: q.bank_code || null, reason: q.reason || '', okDefault: false, origin: 'DRAFT' });
    });
    (this.state.extraQs || []).forEach((q, j) => {
      if (q.g !== 'meet') return;
      rows.push({ key: 'x' + j, text: q.text, kind: 'OPEN', source: 'COUNSELOR', segment_ids: [], bank_code: null, reason: '', okDefault: false, origin: 'NEW' });
    });
    return { saved, rows };
  }

  /** 처리 완료 때 PUT 할 질문 목록. 바뀐 게 없으면 null. */
  questionsToSave() {
    const st = this.state;
    const { saved, rows } = this.qRows();
    const picked = rows
      .filter((r) => (st.qok[r.key] !== undefined ? st.qok[r.key] : r.okDefault))
      .map((r) => ({
        text: String((st.qe[r.key] && st.qe[r.key].text) || r.text).trim(),
        kind: r.kind, source: r.source, segment_ids: r.segment_ids, bank_code: r.kind === 'BANK' ? r.bank_code : null,
      }))
      .filter((q) => q.text);
    const same = picked.length === saved.length && picked.every((q, i) => q.text === saved[i].text);
    return same ? null : picked;
  }

  async saveAll() {
    const { caseId, sid, data, doneHref } = this.props;
    if (this.state.saving) return;
    const st = this.state;
    const { saved, drafts, source } = this.rows();
    const items = [];
    drafts.forEach((x) => {
      const e = st.dr[x.i] || {};
      if (!e.on || e.del) return;
      const text = (e.text !== undefined ? e.text : x.text).trim();
      if (!text) return;
      items.push({ kind: e.kind || 'CHECK', text, due_date: e.due || null, origin: source, edited: text !== x.text, basis: x.basis || [] });
    });
    st.adds.forEach((a) => {
      const text = String(a.text || '').trim();
      if (text) items.push({ kind: a.kind || 'CHECK', text, due_date: a.due || null, origin: 'COUNSELOR', edited: false });
    });
    this.setState({ saving: true, err: '' });
    try {
      for (const x of saved) {
        const e = st.sv[x.id];
        if (!e) continue;
        if (e.del) { await senior.removeNextCheck(caseId, x.id); continue; }
        const body = {};
        if (e.text !== undefined && e.text.trim() && e.text.trim() !== x.text) body.text = e.text.trim();
        if (e.kind && e.kind !== x.kind) body.kind = e.kind;
        if (e.due !== undefined && (e.due || null) !== x.due_date) body.due_date = e.due || null;
        if (Object.keys(body).length) await senior.updateNextCheck(caseId, x.id, body);
      }
      if (items.length) await senior.saveNextChecks(caseId, items, sid);
      const questions = this.questionsToSave();
      if (questions && sid) await followupQuestions.save(sid, questions);
      this.setState({ saving: false, dr: {}, sv: {}, adds: [], editing: false, eText: {}, qok: {}, qe: {}, extraQs: [] });
      window.location.hash = doneHref.slice(1);
    } catch (e) {
      this.setState({ saving: false, err: errText(e, '확인사항 · 추가 질문을 저장하지 못했어요. 잠시 뒤 다시 해 주세요.') });
      data.reload();
    }
  }

  async followup() {
    const { caseId, sid, data } = this.props;
    const fu = this.state.fu;
    if (fu.busy) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fu.date)) { this.setState({ fu: { ...fu, done: '날짜를 골라 주세요.' } }); return; }
    // 이 회차에서 저장한 OPEN 확인사항 가운데 아직 일정에 안 이어진 것을 잇는다(저장 전 초안은 처리 완료 뒤에 다시 이어 주세요).
    const checkIds = (data.data && data.data.checks || [])
      .filter((x) => x.source_session_id === sid && x.status === 'OPEN' && !x.schedule_event_id).map((x) => x.id);
    this.setState({ fu: { ...fu, busy: true, done: '' } });
    try {
      const r = await senior.scheduleFollowup(caseId, { consult_type: fu.type, date: fu.date, time: fu.time || null, place: fu.place.trim() || null, check_ids: checkIds });
      this.setState({ fu: { ...this.state.fu, busy: false, done: `일정을 만들었어요 · ${mdw(r.visit.date)}${r.visit.time ? ' ' + r.visit.time.slice(0, 5) : ''} · 확인사항 ${r.checks.length}건을 이었어요.` } });
      data.reload();
    } catch (e) {
      this.setState({ fu: { ...this.state.fu, busy: false, done: errText(e, '일정을 만들지 못했어요.') } });
    }
  }

  async careStatus(current) {
    const { caseId, data } = this.props;
    const cs = this.state.cs;
    const value = cs.value || current;
    if (cs.busy) return;
    if (!value) { this.setState({ cs: { ...cs, done: '돌봄 상태를 골라 주세요.' } }); return; }
    this.setState({ cs: { ...cs, busy: true, done: '' } });
    try {
      await senior.setCareStatus(caseId, value, cs.note.trim() || null);
      this.setState({ cs: { value: '', note: '', busy: false, done: '저장했어요.' } });
      data.reload();
    } catch (e) {
      this.setState({ cs: { ...this.state.cs, busy: false, done: errText(e, '돌봄 상태를 저장하지 못했어요.') } });
    }
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const st = this.state;
    const { shell, caseId, sid, data, doneHref } = this.props;
    const d = data.data || {};
    const c = d.c;
    const ses = d.session;
    const ctx = { segs: segMap(d.tr), meas: new Map((d.meas || []).map((m) => [m.id, m])) };
    const { saved, drafts } = this.rows();
    const alias = c ? c.child_alias : DASH;
    const nLabel = ses ? `${ses.session_number}회차` : DASH;
    const typeLabel = ses && ses.consultation_type ? CONSULT_LABELS[ses.consultation_type] || DASH : DASH;
    const ids = { caseId, sessionId: sid };
    const why = (basis, kind, due, extra) =>
      [basis, KIND_LABELS[kind] || KIND_LABELS.CHECK, due ? `기한 ${mdw(due)}` : '', extra].filter(Boolean).join(' · ');

    const checks = [];
    saved.forEach((x) => {
      const e = st.sv[x.id] || {};
      if (e.del === 'x') return; // × 로 지운 것은 숨김(저장할 때 지움)
      const text = e.text !== undefined ? e.text : x.text;
      const kind = e.kind || x.kind;
      const due = e.due !== undefined ? e.due : x.due_date || '';
      const key = 's' + x.id;
      checks.push({
        text, on: !e.del, edited: x.edited || text !== x.text,
        why: why(x.origin === 'COUNSELOR' ? '담당자 직접 추가' : basisText(x.basis, ctx), kind, due, e.del ? '저장하면 지워져요' : '저장됨'),
        isEdit: st.editing, notEdit: !st.editing, draft: st.eText[key] !== undefined ? st.eText[key] : text,
        setDraft: (ev) => { const t = ev.target.value; this.setState({ eText: { ...this.state.eText, [key]: t } }); },
        toggle: () => this.patch('sv', x.id, { del: e.del ? false : true }),
        del: () => this.patch('sv', x.id, { del: 'x' }),
        kind, setKind: (ev) => this.patch('sv', x.id, { kind: ev.target.value }),
        due: due || '', setDue: (ev) => this.patch('sv', x.id, { due: ev.target.value }),
      });
    });
    drafts.forEach((x) => {
      const e = st.dr[x.i] || {};
      if (e.del) return;
      const text = e.text !== undefined ? e.text : x.text;
      const kind = e.kind || 'CHECK';
      const key = 'd' + x.i;
      checks.push({
        text, on: !!e.on, edited: text !== x.text,
        why: why(basisText(x.basis, ctx), kind, e.due, '초안'),
        isEdit: st.editing, notEdit: !st.editing, draft: st.eText[key] !== undefined ? st.eText[key] : text,
        setDraft: (ev) => { const t = ev.target.value; this.setState({ eText: { ...this.state.eText, [key]: t } }); },
        toggle: () => this.patch('dr', x.i, { on: !e.on }),
        del: () => this.patch('dr', x.i, { del: true }),
        kind, setKind: (ev) => this.patch('dr', x.i, { kind: ev.target.value }),
        due: e.due || '', setDue: (ev) => this.patch('dr', x.i, { due: ev.target.value }),
      });
    });
    st.adds.forEach((a, j) => {
      if (!st.editing && String(a.text || '').trim()) {
        checks.push({
          text: a.text, on: true, edited: false, why: why('담당자 직접 추가', a.kind, a.due, '저장 전'),
          isEdit: false, notEdit: true, draft: a.text, setDraft: () => {}, toggle: () => {},
          del: () => this.setState({ adds: this.state.adds.filter((_, k) => k !== j) }),
          kind: a.kind, setKind: () => {}, due: a.due || '', setDue: () => {},
        });
      }
    });
    const setAdd = (j, change) => { const n = this.state.adds.slice(); n[j] = { ...n[j], ...change }; this.setState({ adds: n }); };
    const nNewRows = st.editing ? st.adds.map((a, j) => ({
      draft: a.text, setDraft: (ev) => setAdd(j, { text: ev.target.value }),
      kind: a.kind, setKind: (ev) => setAdd(j, { kind: ev.target.value }),
      due: a.due || '', setDue: (ev) => setAdd(j, { due: ev.target.value }),
    })) : [];
    const startN = () => this.setState({ editing: true, eText: {} });
    const addN = () => this.setState({ editing: true, adds: this.state.adds.concat([{ text: '', kind: 'CHECK', due: '' }]) });
    const nOk = () => {
      const s = this.state;
      const sv = { ...s.sv };
      const dr = { ...s.dr };
      Object.keys(s.eText).forEach((key) => {
        const t = String(s.eText[key]).trim();
        if (!t) return;
        if (key[0] === 's') { const id = key.slice(1); sv[id] = { ...(sv[id] || {}), text: t }; }
        else { const i = key.slice(1); dr[i] = { ...(dr[i] || {}), text: t, on: true }; }
      });
      this.setState({ sv, dr, editing: false, eText: {}, adds: s.adds.filter((a) => String(a.text || '').trim()) });
    };
    const nCancel = () => this.setState({ editing: false, eText: {}, adds: this.state.adds.filter((a) => String(a.text || '').trim()) });

    // 추가 질문 — '다음 상담에서 직접' 탭(초안 · 승인한 것 · 직접 쓴 것). '안부 앱으로 먼저' 탭은 안부 앱이 없어 준비 중.
    const { rows: qrows } = this.qRows();
    const qText = (r) => (st.qe[r.key] && st.qe[r.key].text) || r.text;
    const qWhy = (r) => {
      if (r.origin === 'NEW' || r.source === 'COUNSELOR') return '상담사 직접 추가';
      if (r.segment_ids.length) return `${nLabel} ${basisText([{ kind: 'SEGMENT', segment_ids: r.segment_ids }], ctx)}`;
      return r.reason || (r.kind === 'BANK' ? '질문 은행' : DASH);
    };
    const meetQs = qrows.map((r) => {
      const ok = st.qok[r.key] !== undefined ? st.qok[r.key] : r.okDefault;
      const draft = st.qDraft[r.key] || {};
      return {
        id: r.origin === 'NEW' || r.source === 'COUNSELOR' ? '직접 작성' : r.kind === 'BANK' ? '질문 은행' : '열린 질문',
        why: qWhy(r), text: qText(r), opts: [], hasOpts: false, edited: !!st.qe[r.key],
        ok, st: r.origin === 'DRAFT' || r.origin === 'NEW' ? '발송 예약' : '발송 예약 · 저장됨',
        okCls: ok ? 'btn-p' : 'btn-s', okLabel: ok ? '발송 예약 ✓' : '발송 예약',
        isEdit: st.qEditing, notEdit: !st.qEditing, draftText: draft.text !== undefined ? draft.text : qText(r), draftOpts: '',
        approve: () => this.setState({ qok: { ...this.state.qok, [r.key]: !ok }, err: '' }),
        setText: (e) => { const t = e.target.value; this.setState({ qDraft: { ...this.state.qDraft, [r.key]: { text: t } } }); },
        setOpts: () => {},
      };
    });
    const appSoon = {
      id: '준비 중', why: DASH, text: '어르신 안부 앱은 준비 중입니다', opts: [], hasOpts: false, edited: false, ok: false,
      st: '', okCls: 'btn-s', okLabel: '준비 중', isEdit: false, notEdit: true, draftText: '', draftOpts: '',
      approve: () => {}, setText: () => {}, setOpts: () => {},
    };
    const tabMeet = st.tab !== 'app';
    const qs = tabMeet ? (meetQs.length ? meetQs : [{ ...appSoon, id: DASH, text: '이번 회차의 추가 질문 초안이 없어요. 직접 추가할 수 있어요.', okLabel: DASH }]) : [appSoon];
    const qNewRows = tabMeet ? st.qNew.map((r, j) => ({
      ...r, withOpts: false,
      setText: (e) => { const t = e.target.value; const n = this.state.qNew.slice(); n[j] = { ...n[j], text: t }; this.setState({ qNew: n }); },
      setOpts: () => {},
    })) : [];
    const startQ = () => { if (tabMeet) this.setState({ qEditing: true, qDraft: {}, qNew: [] }); };
    const addQ = () => { if (tabMeet) this.setState({ qEditing: true, qNew: (this.state.qEditing ? this.state.qNew : []).concat([{ g: 'meet', text: '', opts: '' }]) }); };
    const qOk = () => {
      const s2 = this.state;
      const qe = { ...s2.qe };
      const qok = { ...s2.qok };
      Object.keys(s2.qDraft).forEach((key) => {
        const t = String(s2.qDraft[key].text || '').trim();
        const row = qrows.find((r) => r.key === key);
        if (!t || !row || t === qText(row)) return;
        qe[key] = { text: t };
      });
      const added = s2.qNew.filter((r) => String(r.text || '').trim()).map((r) => ({ g: 'meet', text: r.text.trim(), opts: [] }));
      const start = (s2.extraQs || []).length;
      added.forEach((_, k) => { qok['x' + (start + k)] = true; }); // 직접 쓴 질문은 고른 채로
      this.setState({ qe, qok, extraQs: (s2.extraQs || []).concat(added), qEditing: false, qDraft: {}, qNew: [] });
    };
    const qCancel = () => this.setState({ qEditing: false, qDraft: {}, qNew: [] });

    const profile = d.profile;
    const current = profile ? profile.care_status : null;
    const linked = saved.filter((x) => x.schedule_event_id && x.due_date);
    const fu = st.fu;
    const cs = st.cs;

    let msg = st.err;
    if (!msg && data.error) msg = errText(data.error, '불러오지 못했어요.');
    if (!msg && data.data && !sid) msg = '이 사례에는 아직 회차가 없어요.';

    return {
      ...base, ...shell,
      checks, nNewRows, addN, startN, nOk, nCancel, nIsEdit: st.editing, nNotEdit: !st.editing,
      qs, qNewRows, addQ, startQ, qOk, qCancel, qIsEdit: st.qEditing, qNotEdit: !st.qEditing,
      kindOpts: Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label })),
      caseHref: href('CaseInfo', { caseId }), historyHref: href('CaseHistory', { caseId }), sessionHref: href('SessionDetail', ids),
      step1Href: carry('#/Step1Record', ids), step2Href: carry('#/Step2Signals', ids), step3Href: carry('#/Step3Summary', ids), step4Href: carry('#/Step4Next', ids),
      crumbCase: c ? `${alias} ${c.case_number}` : DASH, crumbSession: nLabel,
      sub: ses ? `${mdw(ses.consulted_at || ses.created_at)} ${typeLabel}` : DASH,
      title: `${nLabel} 처리 · ${alias}`,
      doneHref, doneLabel: st.saving ? '저장 중…' : `${nLabel} 처리 완료 · 브리핑 보기`,
      done: (e) => { if (e && e.preventDefault) e.preventDefault(); this.saveAll(); },
      msg,
      fu: {
        types: FU_TYPES.map(([value, label]) => ({ value, label })), type: fu.type, date: fu.date, time: fu.time, place: fu.place, min: today(),
        setType: (e) => this.setState({ fu: { ...this.state.fu, type: e.target.value } }),
        setDate: (e) => this.setState({ fu: { ...this.state.fu, date: e.target.value } }),
        setTime: (e) => this.setState({ fu: { ...this.state.fu, time: e.target.value } }),
        setPlace: (e) => this.setState({ fu: { ...this.state.fu, place: e.target.value } }),
        submit: () => this.followup(),
        label: fu.busy ? '만드는 중…' : '재방문 일정 만들기',
        note: fu.done || (linked.length
          ? `이어진 일정: ${[...new Set(linked.map((x) => mdw(x.due_date)))].join(', ')} · 저장한 확인사항 중 일정에 안 이어진 것을 새 일정에 잇습니다.`
          : '저장한 확인사항 중 일정에 안 이어진 것을 새 일정에 잇습니다.'),
      },
      cs: {
        opts: [{ value: '', label: '선택' }].concat(Object.entries(CARE_STATUS_LABELS).map(([value, label]) => ({ value, label }))),
        value: cs.value || current || '', note: cs.note,
        set: (e) => this.setState({ cs: { ...this.state.cs, value: e.target.value, done: '' } }),
        setNote: (e) => this.setState({ cs: { ...this.state.cs, note: e.target.value } }),
        submit: () => this.careStatus(current),
        label: cs.busy ? '저장 중…' : '돌봄 상태 저장',
        status: cs.done || (current
          ? `지금: ${CARE_STATUS_LABELS[current]}${profile.care_status_changed_at ? ` · ${mdw(profile.care_status_changed_at)} 바꿈` : ''}${profile.care_status_note ? ` · ${profile.care_status_note}` : ''}`
          : '아직 정하지 않았어요.'),
      },
    };
  }
}

export default function Step4Next(props) {
  const shell = useShell();
  const { caseId, sessionId } = useIds();
  const [sid, setSid] = useState(sessionId);
  useEffect(() => setSid(sessionId), [sessionId]);
  const data = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const resolved = await resolveSession(cases.listSessions, caseId, sessionId);
    setSid(resolved);
    const [c, profile, meas, checks, session, ana, tr, fq] = await Promise.all([
      cases.get(caseId),
      senior.profile(caseId).catch(() => null),
      senior.measurements(caseId).catch(() => []),
      senior.nextChecks(caseId),
      resolved ? sessions.get(resolved) : null,
      resolved ? analysisApi.get(resolved).catch(() => null) : null,
      resolved ? transcriptApi.get(resolved).catch(() => null) : null,
      resolved ? followupQuestions.get(resolved).catch(() => null) : null,
    ]);
    return { c, profile, meas, checks, session, ana, tr, fq };
  }, [shell.ready, caseId, sessionId]);
  const doneHref = href('CaseInfo', { caseId, sec: 'brief' });
  const v = useDC(Logic, { ...props, shell, caseId, sid, data, doneHref });
  return <View v={v} />;
}
