// 사례 상세(태블릿) — 디자인 CaseInfoTablet.dc.html. 데이터 · 동작은 데스크톱 CaseInfo.jsx 와 같다(Logic 이 export 되지 않아 계산을 그대로 옮겨 왔다).
//  - 태블릿 마크업 차이: 기본 정보에 의뢰 경로 · 담당 상담사 · 접수일 · 배정일 · 초기상담일, 동의 상태는 칩, 건강은 '주호소 · 고려사항' 안 칩.
//    배정일 · 동의 · 비상연락 · 안부 앱은 서버 칸이 없어 '—'.
//  - 오류(불러오기 · 확인 표시 저장 · 후속관리 등록)는 위치 줄 아래 한 줄로 모아 보인다.
// 이하 데스크톱 설명 그대로:
//  - 이름: 실명(personal-info). 부를 때마다 서버에 열람 기록이 남으니 화면을 열 때(사례가 바뀔 때) 한 번만 부른다. 실명이 없으면 별칭.
//  - 고령자 정보: senior-profile(가구형태 · 장기요양 · 건강 · 복약 · 돌봄 필요 · 돌봄 상태) · health-trend(최근 측정 · 지난번 값).
//  - 브리핑: senior-brief(요약 · 확인사항 초안 · 아직 안 끝난 확인사항 · 최근 영역 변화 · 다음 방문).
//  - 진행 상황: 가장 최근 회차 상태로 1~4단계 위치.
//  - 고령자에는 위기도 판정이 없다 — 칩은 디자인대로 두고 '—'. 서버에 없는 칸(주호소 · 상담 영역 · 키워드 · 동의 · 안부 앱 등)도 '—'.
//  - 녹음하기 · 녹취 올리기는 Upload 화면으로(이 사례를 싣고).
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/CaseInfoTablet.logic';
import { cases } from '@cw/api/endpoints';
import { senior, CARE_GRADE_LABELS, CARE_NEED_LABELS, CARE_STATUS_LABELS, LIVING_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, age, genderLabel, md, ymd, or } from '../data/format';
import { caseLinks, kindLabel, stepOf, stepLook, subLine, visitType, visitWhen } from './CaseInfo.parts';
import View from './CaseInfoTablet.view';

const STEP_NAMES = ['기록 확인', '정서·위기 신호 확인', '상담일지 작성', '다음 상담 준비'];
// 디자인의 세 가지 단계 모양(끝남 · 지금 · 남음) 그대로.
const DOT = {
  done: { background: '#ECF5FA', color: '#55687A' },
  cur: { background: '#FFFFFF', border: '2px solid #1F3A56', color: '#1F3A56' },
  todo: { background: '#DDE6EC', color: '#66788A' },
};
const LABEL = { done: { color: '#55687A' }, cur: { fontWeight: '700', color: '#1F3A56' }, todo: { color: '#66788A' } };

const chips = (list) => (list.length ? list : [DASH]);
const soft = (p) => p.catch(() => null);

/** 이름 가리기(인쇄): 김순자 → 김○자, 순자 → 순○ — 디자인 nmMask 와 같은 규칙을 이 사례 이름에 쓴다. */
function maskNames(text, names) {
  let r = String(text || '');
  names.forEach((n) => {
    if (n && n.length >= 2) r = r.split(n).join(n[0] + '○' + n.slice(2));
  });
  names.forEach((n) => {
    if (n && n.length >= 3) {
      const g = n.slice(1);
      r = r.split(g).join(g[0] + '○');
    }
  });
  return r;
}

function trendChips(trend) {
  if (!trend || !trend.metrics) return [];
  const by = Object.fromEntries(trend.metrics.map((m) => [m.metric, m]));
  const num = (x) => (x === null || x === undefined ? DASH : String(Number(x)));
  const out = [];
  const sys = by.systolic;
  const dia = by.diastolic;
  if (sys || dia) {
    const now = `${num(sys && sys.latest && sys.latest.value)}/${num(dia && dia.latest && dia.latest.value)}`;
    const prev = sys && sys.previous ? `${num(sys.previous.value)}/${num(dia && dia.previous && dia.previous.value)}` : null;
    out.push(`혈압 ${now}mmHg${prev ? ` (지난번 ${prev})` : ''}`);
  }
  trend.metrics.forEach((m) => {
    if (m.metric === 'systolic' || m.metric === 'diastolic' || !m.latest) return;
    const unit = m.max_value ? `/${num(m.max_value)}` : m.unit || '';
    out.push(`${m.label} ${num(m.latest.value)}${unit}${m.previous ? ` (지난번 ${num(m.previous.value)})` : ''}`);
  });
  if (trend.last_measured_at) out.push(`마지막 측정 ${ymd(trend.last_measured_at)}`);
  return out;
}

class Logic extends DesignLogic {
  names() {
    const { data, pi } = this.props;
    const c = data && data.c;
    return [pi && pi.child_name, c && c.child_alias].filter(Boolean);
  }

  // 인쇄 '이름 가리기' — 예시 이름 대신 이 사례의 실명 · 별칭을 가린다.
  nmMask(t) {
    return maskNames(t, this.names());
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { data, pi, caseId, shell, closure } = this.props;
    const d = data || {};
    const c = d.c;
    const p = d.profile;
    const brief = d.brief;
    const sessions = d.sessions || [];
    const latest = sessions[0] || null;
    const links = caseLinks(caseId, latest && latest.id);
    const name = (pi && pi.child_name) || (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;
    const nv = brief && brief.next_visit;
    const nextNo = latest ? latest.session_number + 1 : 1;

    // 기본 정보
    const a = c ? age(c.child_birth_year) : null;
    const g = c ? genderLabel(c.child_gender) : DASH;
    const birth = pi && pi.child_birth_date ? pi.child_birth_date : c && c.child_birth_year ? `${c.child_birth_year}년생` : null;
    const fam = pi && pi.family_members && pi.family_members[0];
    const famMeta = fam
      ? [fam.relation, fam.age != null ? `만 ${fam.age}세` : null, fam.living_together === true ? '동거' : fam.living_together === false ? '따로 삶' : null].filter(Boolean).join(' · ')
      : '';
    const carer = fam ? [fam.name, famMeta].filter(Boolean).join(' / ') : DASH;
    const first = sessions.length ? sessions[sessions.length - 1] : null;
    const firstDate = (c && c.first_interview_date) || (first && first.consulted_at);
    const living = p && p.living_arrangement ? LIVING_LABELS[p.living_arrangement] : DASH;

    // 건강 · 돌봄(고령자 정보)
    const health = [];
    if (p && p.health_notes) health.push(p.health_notes);
    if (p && p.takes_medication === true) health.push(p.medication_notes ? `복약 (${p.medication_notes})` : '복약 중');
    if (p && p.takes_medication === false) health.push('복약 없음');
    if (p && p.care_grade) health.push(CARE_GRADE_LABELS[p.care_grade]);
    trendChips(d.trend).forEach((x) => health.push(x));
    const care = [];
    if (p) (p.care_needs || []).forEach((n) => care.push(`${CARE_NEED_LABELS[n] || n} 필요`));
    if (p && p.care_needs_note) care.push(p.care_needs_note);
    if (p && p.care_notes) care.push(p.care_notes);
    const careStatus = p && p.care_status ? CARE_STATUS_LABELS[p.care_status] : null;

    // 진행 상황(가장 최근 회차)
    const cur = stepOf(latest, { domainsConfirmed: !!(d.domains && d.domains.confirmed), checksSaved: !!d.checksSaved });
    const recLook = !latest ? 'todo' : cur === 0 ? 'cur' : 'done';
    const steps = STEP_NAMES.map((label, i) => {
      const look = latest ? stepLook(i + 1, cur) : 'todo';
      return { label, href: links.stepHrefs[i], dot: DOT[look], lab: LABEL[look], mark: look === 'done' ? '✓' : String(i + 1) };
    });
    const ST1 = { STT_PROCESSING: '변환 중', AUDIO_UPLOADED: '변환 대기', STT_FAILED: '변환 실패', STT_REVIEW_REQUIRED: '검수 대기' };
    const st1Chip = latest && cur === 1 ? ST1[latest.status] || null : null;
    const curIdx = cur >= 1 && cur <= 4 ? cur - 1 : 0;
    const toUpload = !latest || cur === 0;
    const contHref = toUpload ? links.uploadHref : cur === 5 ? href('SessionDetail', { caseId, sessionId: latest.id }) : links.stepHrefs[curIdx];
    const contLabel = toUpload ? '녹취 올리기' : cur === 5 ? '회차 상세' : STEP_NAMES[curIdx];

    // 브리핑
    const sesNo = Object.fromEntries(sessions.map((s) => [s.id, s.session_number]));
    const change = brief && brief.recent_changes && brief.recent_changes[0];
    const checks = (brief && brief.open_checks) || [];
    const draftRows = brief
      ? [{ chip: '요약', text: brief.summary }].concat((brief.check_items || []).map((x) => ({ chip: '확인 초안', text: x.text })))
      : [];

    return {
      ...base,
      ...shell,
      ...links,
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, p),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${nv ? visitWhen(nv.date, nv.time) : DASH}`,
      caseLabel: `${name} · ${no}`,
      // 기본 정보
      kvNo: no,
      kvName: name === DASH ? DASH : `${name} (${g}) · 호칭 "${name} 님"`,
      kvBirth: birth ? `${birth}${a !== null ? ` (만 ${a}세)` : ''}` : DASH,
      kvLiving: living,
      kvCarer: carer,
      kvEmergency: DASH,
      kvConsent: DASH,
      kvReferral: or(c && c.linked_background),
      kvCounselor: or(c && c.counselor_name),
      kvReport: or(c && c.report_date),
      kvAssigned: DASH,
      kvFirst: firstDate ? `${ymd(firstDate)}${first && first.consultation_type ? ` (${kindLabel(first.consultation_type)})` : ''}` : DASH,
      kvCount: c ? `${c.session_count ?? sessions.length}회` : DASH,
      kvLatest: latest ? `${ymd(latest.consulted_at || latest.created_at)} · ${kindLabel(latest.consultation_type)}` : DASH,
      kvApp: DASH,
      // 신체 · 정신건강(11/17 새 디자인). 정신건강 상태 · 심리검사 · 장애 등급은 서버 칸이 없어 '—'(진단 · 판정을 쓰지 않는다).
      kvDisease: or(p && p.health_notes),
      kvMeds: p && p.takes_medication === true ? (p.medication_notes ? `복약 중 · ${p.medication_notes}` : '복약 중') : p && p.takes_medication === false ? '복약 없음' : DASH,
      kvMental: DASH,
      kvTest: DASH,
      kvDisability: DASH,
      kvGrade: p && p.care_grade ? CARE_GRADE_LABELS[p.care_grade] : DASH,
      trHref: latest ? links.stepHrefs[0] : links.uploadHref,
      trLabel: latest ? `${latest.session_number}회차 축어록 보기 (${md(latest.consulted_at || latest.created_at)}) →` : '녹취 올리기 →',
      // 주호소 · 고려사항(돌봄 상태는 위기도 칩 자리에 — 고령자의 상담사 지정 값)
      careChip: careStatus || DASH,
      careCls: careStatus ? 'chip c-check' : 'chip c-lo',
      careNote: careStatus && p.care_status_changed_at ? `상담사 지정 · ${md(p.care_status_changed_at)}` : DASH,
      complaint: or(c && c.intake_problem),
      areaChips: chips([]),
      keywordChips: chips([]),
      commChips: chips([]),
      healthChips: chips(health),
      serviceChips: chips(care),
      // 진행 상황
      progNote: latest ? `${latest.session_number}회차 (${md(latest.consulted_at || latest.created_at)})` : DASH,
      contHref,
      contLabel: `이어서 하기 · ${contLabel}`,
      recDot: DOT[recLook],
      recMark: recLook === 'done' ? '✓' : '·',
      recDate: latest && latest.consulted_at ? md(latest.consulted_at) : DASH,
      steps,
      st1Chip,
      // 브리핑
      briefSub: nv ? `${visitWhen(nv.date, nv.time)} · ${nextNo}회차 ${visitType(nv.consult_type)}${nv.place ? ` · ${nv.place}` : ''}` : `다음 방문 일정 ${DASH}`,
      lead1: DASH,
      lead1Src: DASH,
      lead2Q: DASH,
      lead2Has: false,
      lead2: DASH,
      lead2Src: DASH,
      lead3Q: change ? `${change.label}${change.change_note ? ` · ${change.change_note}` : ''}` : DASH,
      lead3: change && change.text ? `"${change.text}"` : DASH,
      lead3Src: change ? `${change.session_number}회차 · ${md(change.date)}` : DASH,
      checkRows: checks.map((x) => ({
        done: !!(this.props.checkDone || {})[x.id],
        toggle: (e) => this.props.toggleCheck(x.id, e.target.checked),
        text: `${x.kind === 'ACTION' ? '[할 일] ' : ''}${x.text}`,
        src: [
          x.source_session_id && sesNo[x.source_session_id] ? `근거 · ${sesNo[x.source_session_id]}회차` : '근거 · 상담사 입력',
          x.due_date ? `기한 ${md(x.due_date)}` : null,
        ].filter(Boolean).join(' · '),
      })),
      checkEmpty: checks.length === 0,
      checksHref: href('Step4Next', { caseId, sessionId: latest && latest.id, sec: 'next-checks' }),
      nextHref: href('Step4Next', { caseId, sessionId: latest && latest.id }),
      draftChip: brief && brief.source === 'RULE' ? '자동 초안' : 'AI 초안',
      draftRows: draftRows.length ? draftRows : [{ chip: DASH, text: DASH }],
      // 기관 서식 · 종결 검토
      formChip: DASH,
      isReg: !!(c && c.closure_review_at),
      notReg: !!c && !c.closure_review_at,
      reg: () => closure('register'),
      unreg: () => closure('cancel'),
      closureErr: this.props.closureErr,
      checkErr: this.props.checkErr,
      loadErr: this.props.loadErr,
      // 태블릿 마크업에만 있는 값
      alertMsg: this.props.loadErr || this.props.checkErr || this.props.closureErr || '',
      consentChips: [{ text: DASH, cls: 'chip c-lo' }],
      docsHref: href('CaseDocs', { caseId }),
      appHref: href('CaseApp', { caseId }),
      formHref: href('CaseForm', { caseId }),
      step1Href: links.stepHrefs[0],
      navLinkCnt: '',
      navFollowCnt: '',
    };
  }

  renderVals() {
    const v = super.renderVals();
    const nm = this.names()[0] || '';
    return {
      ...v,
      recOpen: v.goUpload,
      outOpts: (v.outOpts || []).map((o, i) => ({ ...o, ex: `예) ${nm ? (i === 0 ? nm : maskNames(nm, [nm])) : DASH}` })),
    };
  }
}

export default function CaseInfoTablet(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const [closureErr, setClosureErr] = useState('');
  // 확인할 사항 체크: 누르면 끝남(DONE), 다시 풀면 열림(OPEN). 목록은 열린 것만 오니, 이번에 체크한 줄은 다시 불러오기 전까지 체크된 채 남는다.
  const [checkDone, setCheckDone] = useState({});
  const [checkErr, setCheckErr] = useState('');
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, trend, brief, sessionsPage, checks] = await Promise.all([
      cases.get(caseId),
      soft(senior.profile(caseId)),
      soft(senior.trend(caseId)),
      soft(senior.brief(caseId)),
      soft(cases.listSessions(caseId, { page_size: 100 })),
      soft(senior.nextChecks(caseId)),
    ]);
    const sessions = sessionsPage ? [...sessionsPage.items].sort((a, b) => b.session_number - a.session_number) : [];
    const latest = sessions[0];
    const domains = latest && latest.status === 'AI_REVIEW_REQUIRED' ? await soft(senior.sessionDomains(latest.id)) : null;
    const checksSaved = !!(latest && checks && checks.some((x) => x.source_session_id === latest.id));
    return { c, profile, trend, brief, sessions, domains, checksSaved };
  }, [shell.ready, caseId]);
  // 실명 · 생년월일 · 가족: 열람 기록이 남으니 사례가 바뀔 때만 한 번 부른다(새로 읽기 · 종결 등록 때는 다시 부르지 않는다).
  const personal = useAsync(() => (shell.ready && caseId ? cases.getPersonalInfo(caseId) : null), [shell.ready, caseId]);

  const closure = (what) => {
    setClosureErr('');
    const call = what === 'register' ? cases.registerClosureReview(caseId) : cases.cancelClosureReview(caseId);
    call.then(
      () => main.reload(),
      (e) => setClosureErr((e && e.message) || '종결 검토 등록을 바꾸지 못했어요. 잠시 뒤 다시 해 주세요.'),
    );
  };
  const toggleCheck = (id, on) => {
    setCheckErr('');
    setCheckDone((m) => ({ ...m, [id]: on }));
    senior.updateNextCheck(caseId, id, { status: on ? 'DONE' : 'OPEN' }).catch((e) => {
      setCheckDone((m) => ({ ...m, [id]: !on }));
      setCheckErr((e && e.message) || '확인 표시를 저장하지 못했어요. 잠시 뒤 다시 해 주세요.');
    });
  };
  let loadErr = '';
  if (!caseId) loadErr = '사례를 고르지 않았어요. 사례 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '사례 정보를 불러오지 못했어요.';

  const v = useDC(Logic, { ...props, shell, caseId, data: main.data, pi: personal.data, closure, closureErr, loadErr, checkDone, checkErr, toggleCheck });
  return <View v={v} />;
}
