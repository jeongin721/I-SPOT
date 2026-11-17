// 사례 상세 · 초기상담지(시니어용) — 디자인 CaseIntake.dc.html. ?case=<id>.
// 새 대상자 등록(CaseRegister.jsx)이 저장한 칸을 읽어 같은 서식에 채우고, '확정' 을 누르면 바뀐 칸만 다시 저장한다.
//  읽기: cases.get(사례) · cases.getPersonalInfo(실명 · 생년월일 · 주 돌봄자 · 가족관계 · 건강 상태 — 열람 기록이 남으니 화면을 열 때 한 번)
//        · senior.profile(가구형태 · 장기요양등급 · 복약 · 낙상 · 돌봄 필요) · senior.overview(머리의 다음 상담).
//  저장(칸 규칙은 CaseRegister.jsx 와 같다): 화면을 연 때 값과 비교해 바뀐 것만 보낸다.
//   - PATCH /cases/{id}: 이름(별칭 · 제목) · 출생연도 · 성별 · 날짜 셋 · 의뢰 경로/의뢰인(linked_background) · 주호소 · 돌봄자 관계 · 주호소 상세(notes) · 태도 · 환경 · 소견.
//   - PUT /cases/{id}/personal-info: 실명 · 생년월일 · 주 돌봄자 · 가족관계 표(이 화면에 없는 종교 · 학력 · 직업은 그대로 둔다) · 건강 상태 표(바꿨을 때만 다시 만든다).
//   - PATCH /cases/{id}/senior-profile: 가구형태 · 장기요양등급 · 주요 질환 · 장애 · 복용 약 · 최근 낙상 · 도움 필요 활동
//     (care_notes 의 다른 줄, 이 서식에 없는 돌봄 필요 값 — 정서 지원 · 안부 확인 · 병원 동행 — 은 지우지 않는다).
//  사례번호는 서버가 바꾸지 못하게 해 읽기만. 담당 상담사도 읽기만.
//  서버에 칸이 없어 화면에서만 바뀌고 저장하지 않는 것(CaseRegister 와 같다): 주 상담 영역 · 위기도(초기 판단) · 연락처 · 주소 · 비상연락 가족 ·
//   상담 동의 · 대리 동의 사유 · 가족 정보 공유 범위 · 녹음 동의 · 공유 범위 메모 · 의사소통 고려사항 · 주요 어려움 ·
//   가족관계 표의 연락처 · 거주지 · 연락 빈도 · 사회관계 · 경제 · 이용 중인 서비스. 그래서 이 칸들은 처음에 비어 있다('선택').
//  '임시 저장' 은 서버 기능이 없어 안내만 한다.
import { useDC } from '../dc';
import DesignLogic from '../design/CaseIntake.logic';
import { cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, ymd, hm } from '../data/format';
import { caseLinks, subLine, visitWhen } from './CaseInfo.parts';
import View from './CaseIntake.view';

const isDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(new Date(v).getTime());
const t = (v) => String(v || '').trim();
const orNull = (v) => t(v) || null;
const picked = (v) => (t(v) && v !== '선택' ? t(v) : '');
const soft = (p) => p.catch(() => null);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const DATES = { report: '상담 접수일', link: '의뢰일', first: '초기상담일', birth: '생년월일', tbirth: '주 돌봄자 생년월일' };
// 디자인 서식의 고르기 값(되읽을 때 서식에 있는 값만 고른다).
const RELS = ['배우자', '아들', '딸', '며느리', '사위', '손자녀', '형제자매', '친척', '이웃 · 지인', '없음', '기타'];
const M1 = ['본인', '가족', '행정복지센터(읍·면·동)', '노인맞춤돌봄 수행기관(생활지원사)', '의료기관', '치매안심센터', '정신건강복지센터', '노인복지관 · 경로당', '이웃 · 지인', '기타'];
const FAM = ['독거', '독거(자녀 인근 거주)', '부부', '자녀동거', '조손', '형제 · 친척 동거', '비혈연 동거', '시설 거주', '기타'];
const TR = ['식사하기', '옷 입기', '세수 · 목욕', '화장실 이용', '실내 이동', '계단 오르기', '식사 준비', '장보기', '청소 · 빨래', '약 챙겨 먹기', '전화 사용', '금전 관리', '교통수단 이용', '혼자 외출', '도움 필요 없음', '기타'];

// CaseRegister.jsx 와 같은 저장 규칙.
const LIVING = {
  '독거': 'ALONE', '독거(자녀 인근 거주)': 'ALONE', '부부': 'COUPLE', '자녀동거': 'WITH_FAMILY', '조손': 'WITH_FAMILY',
  '형제 · 친척 동거': 'WITH_FAMILY', '비혈연 동거': 'OTHER', '시설 거주': 'FACILITY', '기타': 'OTHER',
};
const PLAIN_LIVING = { '독거': 1, '부부': 1, '자녀동거': 1 };
const LIVING_BACK = { ALONE: '독거', COUPLE: '부부', WITH_FAMILY: '자녀동거', FACILITY: '시설 거주', OTHER: '기타' };
const NEEDS = {
  '식사하기': 'MEAL', '식사 준비': 'MEAL', '청소 · 빨래': 'HOUSEWORK', '장보기': 'HOUSEWORK', '실내 이동': 'MOBILITY',
  '계단 오르기': 'MOBILITY', '교통수단 이용': 'MOBILITY', '혼자 외출': 'MOBILITY', '약 챙겨 먹기': 'MEDICATION',
};
// 이 서식의 '도움 필요 활동' 으로는 고를 수 없는 돌봄 필요 값 — 저장할 때 지우지 않는다.
const KEEP_NEEDS = ['HOSPITAL_ESCORT', 'EMOTIONAL', 'SAFETY_CHECK'];
const GRADE_BACK = { COGNITIVE_SUPPORT: '인지지원등급', NONE: '없음', UNKNOWN: '등급 모름' };
const X_KEYS = ['referrer', 'guardRel', 'detail', 'hsName', 'disName', 'dsbName', 'hospN', 'hospY', 'hospM', 'psyName', 'medY', 'medM', 'cnsWhy', 'cnsN', 'cnsY', 'cnsM', 'meds', 'grade', 'fall', 'attitude', 'env', 'opinion'];

function alias(name) {
  return name.length >= 2 ? name[0] + '○' + name.slice(2) : name;
}
function careGrade(text) {
  const v = t(text);
  if (!v) return null;
  const m = /([1-5])\s*등급/.exec(v);
  if (m) return `GRADE_${m[1]}`;
  if (/인지/.test(v)) return 'COGNITIVE_SUPPORT';
  if (/^없음|해당\s*없/.test(v)) return 'NONE';
  return 'UNKNOWN';
}
function together(v) {
  const s = t(v);
  if (!s) return null;
  if (/비동거|별거|아니|아님|x|n/i.test(s)) return false;
  if (/동거|예|o|y/i.test(s)) return true;
  return null;
}
const period = (y, m) => (t(y) || t(m) ? `총 ${t(y) || 0}년 ${t(m) || 0}개월` : '');
const yn = (v) => (v === '유' ? true : v === '무' ? false : null);
const ynBack = (b) => (b === true ? '유' : b === false ? '무' : '');
const join = (arr, sep = ' · ') => arr.filter(Boolean).join(sep);
const cut = (v, n) => (v && v.length > n ? v.slice(0, n) : v);

/** 이름 가리기: 김순자 → 김○자, 순자 → 순○ (CaseInfo 와 같은 규칙). */
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

/** 'N회 · 입원·통원 · 총 Y년 M개월' 같은 건강 상태 세부를 조각으로 다시 나눈다(CaseRegister 가 이어 붙인 모양). */
function splitDetail(detail) {
  const out = { rest: [], n: '', y: '', m: '', types: {}, level: '', med: '', medY: '', medM: '' };
  String(detail || '').split(' · ').map((x) => x.trim()).filter(Boolean).forEach((part) => {
    let mm;
    if ((mm = /^(\d+)회$/.exec(part))) out.n = mm[1];
    else if ((mm = /^관련 약 복용 안 함$/.exec(part))) out.med = '무';
    else if ((mm = /^관련 약 복용(?: 총 (\d+)년 (\d+)개월)?$/.exec(part))) { out.med = '유'; out.medY = mm[1] || ''; out.medM = mm[2] || ''; }
    else if ((mm = /^총 (\d+)년 (\d+)개월$/.exec(part))) { out.y = mm[1]; out.m = mm[2]; }
    else if (/^(입원|통원)(·(입원|통원))?$/.test(part)) part.split('·').forEach((k) => { out.types[k] = true; });
    else if ((mm = /^(심한|심하지 않은) 장애$/.exec(part))) out.level = mm[1];
    else out.rest.push(part);
  });
  return out;
}

/** 서버 값 → 서식 상태(f · x · fr · hs · fam · tr). */
function fromServer(c, pi, p) {
  const P = pi || {};
  const tp = P.target_person || {};
  const lb = String((c && c.linked_background) || '');
  let m1 = '';
  let referrer = '';
  const lbParts = lb.split(' · ');
  if (lb && lbParts.every((x) => /^의뢰 경로: |^의뢰인: /.test(x))) {
    lbParts.forEach((x) => {
      if (x.startsWith('의뢰 경로: ')) m1 = x.slice(7);
      else referrer = x.slice(5);
    });
  } else referrer = lb;
  const f = {
    report: (c && c.report_date) || '',
    link: (c && c.linked_date) || '',
    first: (c && c.first_interview_date) || '',
    no: (c && c.case_number) || '',
    name: P.child_name || '',
    sex: c && c.child_gender === 'F' ? '여' : c && c.child_gender === 'M' ? '남' : '선택',
    birth: P.child_birth_date || '',
    target: tp.name || '',
    rel: RELS.includes(tp.relation) ? tp.relation : '선택',
    tbirth: tp.birth_date || '',
    m1: M1.includes(m1) ? m1 : '선택',
    m2: '선택',
    how: (c && c.intake_problem) || '',
    consent: '선택',
    share: '선택',
  };
  if (m1 && !M1.includes(m1)) referrer = join([`의뢰 경로: ${m1}`, referrer]);

  // 건강 상태 표(personal_info.health) — 없으면 profile.health_notes 를 질환 칸에.
  const x = {};
  X_KEYS.forEach((k) => { x[k] = ''; });
  Object.assign(x, {
    referrer,
    guardRel: (c && c.intake_guardian_relation) || '',
    detail: (c && c.notes) || '',
    attitude: (c && c.intake_attitude) || '',
    env: (c && c.intake_environment) || '',
    opinion: (c && c.intake_opinion) || '',
  });
  const hs = {};
  const H = P.health;
  if (H) {
    x.hsName = H.subject_name || '';
    const by = Object.fromEntries((H.items || []).map((i) => [i.kind, i]));
    const it = (k) => by[k] || { present: null, detail: '' };
    hs.dis = ynBack(it('질병').present);
    x.disName = it('질병').detail || '';
    const dsb = splitDetail(it('장애').detail);
    hs.dsb = ynBack(it('장애').present);
    x.dsbName = dsb.rest.join(' · ');
    hs.dsbLv = dsb.level;
    const hosp = splitDetail(it('병원치료').detail);
    hs.hosp = ynBack(it('병원치료').present);
    x.hospN = hosp.n; x.hospY = hosp.y; x.hospM = hosp.m;
    hs.hospT = hosp.types;
    const psy = splitDetail(it('정신과 진단').detail);
    hs.psy = ynBack(it('정신과 진단').present);
    x.psyName = psy.rest.join(' · ');
    hs.med = psy.med; x.medY = psy.medY; x.medM = psy.medM;
    const cns = splitDetail(it('타기관 상담').detail);
    hs.cns = ynBack(it('타기관 상담').present);
    x.cnsWhy = cns.rest.join(' · ');
    x.cnsN = cns.n; x.cnsY = cns.y; x.cnsM = cns.m;
  } else if (p && p.health_notes) {
    const hn = String(p.health_notes);
    const dis = /주요 질환: ([^\n]*?)(?: · 장애: |$)/.exec(hn);
    const dsb = /장애: (.*)$/.exec(hn);
    x.disName = dis ? dis[1] : /장애: /.test(hn) ? '' : hn;
    x.dsbName = dsb ? dsb[1] : '';
    if (x.disName) hs.dis = '유';
    if (x.dsbName) hs.dsb = '유';
  }

  // 고령자 기본정보(senior-profile)
  let fam = '';
  let famOther = '';
  const extraNotes = [];
  if (p) {
    String(p.care_notes || '').split('\n').forEach((line) => {
      if (line.startsWith('가구형태: ')) {
        const v = line.slice(6);
        const hit = FAM.find((k) => v === k || v.startsWith(`${k}: `));
        if (hit) { fam = hit; famOther = v.length > hit.length ? v.slice(hit.length + 2) : ''; } else { fam = '기타'; famOther = v; }
      } else if (line.startsWith('최근 낙상: ')) x.fall = line.slice(7);
      else if (line.trim()) extraNotes.push(line);
    });
    if (!fam && p.living_arrangement) fam = LIVING_BACK[p.living_arrangement] || '';
    const g = p.care_grade;
    x.grade = g ? (/^GRADE_(\d)$/.test(g) ? `${g.slice(6)}등급` : GRADE_BACK[g] || '') : '';
    x.meds = p.takes_medication === false ? '없음' : p.medication_notes || '';
  }
  const tr = {};
  let trOther = '';
  if (p && p.care_needs_note) {
    p.care_needs_note.split(' · ').forEach((k) => {
      if (k.startsWith('기타: ')) { tr['기타'] = true; trOther = k.slice(4); } else if (TR.includes(k)) tr[k] = true;
    });
  }
  const fr = (P.family_members || []).map((m) => ({
    name: m.name || '', rel: m.relation || '', age: m.age != null ? String(m.age) : '',
    live: m.living_together === true ? '동거' : m.living_together === false ? '비동거' : '',
  }));
  while (fr.length < 2) fr.push({});
  return {
    f, x, fr, hs, fam, famOther, famEdit: '', tr, trOther, trEdit: false, hm: {}, hmOther: '', hmEdit: false, ty: {},
    extraNotes, keepNeeds: ((p && p.care_needs) || []).filter((n) => KEEP_NEEDS.includes(n)),
  };
}

/** 서식 상태 → 저장할 값 세 묶음(비교용). CaseRegister.jsx payload() 와 같은 규칙. */
function toServer(s) {
  const f = s.f;
  const x = s.x;
  const H = s.hs || {};
  const name = t(f.name);
  const caregiver = t(f.target) && t(f.target) !== '없음' ? t(f.target) : null;
  const rel = picked(f.rel) && f.rel !== '없음' ? f.rel : null;
  const family = s.fr.filter((r) => t(r.name)).map((r) => {
    const a = parseInt(t(r.age), 10);
    return { name: cut(t(r.name), 50), relation: cut(orNull(r.rel), 30), age: Number.isFinite(a) && a >= 0 && a <= 150 ? a : null, living_together: together(r.live) };
  });
  const hospT = Object.keys(H.hospT || {}).filter((k) => H.hospT[k]).join('·');
  const items = [
    { kind: '질병', present: yn(H.dis), detail: join([t(x.disName)]) },
    { kind: '장애', present: yn(H.dsb), detail: join([t(x.dsbName), H.dsbLv ? `${H.dsbLv} 장애` : '']) },
    { kind: '병원치료', present: yn(H.hosp), detail: join([t(x.hospN) ? `${t(x.hospN)}회` : '', hospT, period(x.hospY, x.hospM)]) },
    { kind: '정신과 진단', present: yn(H.psy), detail: join([t(x.psyName), H.med === '유' ? join(['관련 약 복용', period(x.medY, x.medM)], ' ') : H.med === '무' ? '관련 약 복용 안 함' : '']) },
    { kind: '타기관 상담', present: yn(H.cns), detail: join([t(x.cnsWhy), t(x.cnsN) ? `${t(x.cnsN)}회` : '', period(x.cnsY, x.cnsM)]) },
  ].filter((i) => i.present !== null || i.detail).map((i) => ({ ...i, detail: cut(i.detail, 200) || null }));
  const health = items.length || t(x.hsName) ? { subject_name: cut(orNull(x.hsName), 50), items } : null;

  const body = {
    name,
    child_birth_year: isDate(f.birth) ? Number(f.birth.slice(0, 4)) : null,
    child_gender: f.sex === '여' ? 'F' : f.sex === '남' ? 'M' : null,
    report_date: orNull(f.report),
    linked_date: orNull(f.link),
    first_interview_date: orNull(f.first),
    linked_background: cut(join([picked(f.m1) ? `의뢰 경로: ${f.m1}` : '', t(x.referrer) ? `의뢰인: ${t(x.referrer)}` : '']), 2000) || null,
    intake_problem: cut(orNull(f.how), 2000),
    intake_guardian_relation: cut(orNull(x.guardRel), 2000),
    intake_attitude: cut(orNull(x.attitude), 2000),
    intake_environment: cut(orNull(x.env), 2000),
    intake_opinion: cut(orNull(x.opinion), 2000),
    notes: cut(orNull(x.detail), 4000),
  };
  const pi = {
    child_name: cut(name, 50) || null,
    child_birth_date: orNull(f.birth),
    target_person: caregiver ? { name: cut(caregiver, 50), relation: rel, birth_date: isDate(f.tbirth) ? f.tbirth : null } : null,
    family_members: family.slice(0, 30),
    health,
  };
  const fam = s.fam || '';
  const famText = fam ? `${fam}${s.famOther ? `: ${s.famOther}` : ''}` : '';
  const trOn = Object.keys(s.tr || {}).filter((k) => s.tr[k] && k !== '도움 필요 없음');
  const needs = [...new Set(trOn.map((k) => NEEDS[k] || 'OTHER').concat(s.keepNeeds || []))];
  const meds = t(x.meds);
  const profile = {
    living_arrangement: fam ? LIVING[fam] || 'OTHER' : null,
    care_grade: careGrade(x.grade),
    health_notes: cut(join([t(x.disName) ? `주요 질환: ${t(x.disName)}` : '', t(x.dsbName) ? `장애: ${t(x.dsbName)}` : '']), 2000) || null,
    takes_medication: meds ? !/^없음/.test(meds) : H.med === '유' ? true : null,
    medication_notes: meds && !/^없음/.test(meds) ? cut(meds, 2000) : null,
    care_notes: cut(join([famText && !PLAIN_LIVING[fam] ? `가구형태: ${famText}` : '', t(x.fall) ? `최근 낙상: ${t(x.fall)}` : ''].concat(s.extraNotes || []), '\n'), 2000) || null,
    care_needs: needs,
    care_needs_note: cut(join(trOn.map((k) => (k === '기타' && s.trOther ? `기타: ${s.trOther}` : k))), 2000) || null,
  };
  return { body, pi, profile };
}

function changed(now, was) {
  const out = {};
  Object.keys(now).forEach((k) => {
    if (!same(now[k], was[k])) out[k] = now[k];
  });
  return out;
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    // 디자인 예시(김순자 · 접수일 · 고른 칩들)는 지우고 빈 서식으로 시작 — 서버 값이 오면 채운다.
    const blank = fromServer(null, null, null);
    this.state = { ...this.state, ...blank, rows: 2, tried: false, busy: false, err: '', ok: '' };
    this._loaded = null;
    this._snap = null;
    this._pi = null;
  }

  names() {
    const { data } = this.props;
    const c = data && data.c;
    return [this._pi && this._pi.child_name, c && c.child_alias].filter(Boolean);
  }

  nmMask(text) {
    return maskNames(text, this.names());
  }

  // 서버 값이 처음 도착하면 서식 상태를 채운다(그리기 전에 바로 넣어 깜빡임 없이).
  fill() {
    const { data, pi, caseId } = this.props;
    if (!data || !data.c || !pi || data.c.id !== caseId) return;
    const key = caseId;
    if (this._loaded === key) return;
    this._loaded = key;
    this._pi = pi;
    const st = fromServer(data.c, pi, data.profile);
    this.state = { ...this.state, ...st, rows: st.fr.length, err: '', ok: '' };
    this._snap = toServer(this.state);
  }

  async save() {
    const s = this.state;
    const { caseId } = this.props;
    if (s.busy || !this._snap) return;
    const bad = Object.keys(DATES).filter((k) => t(s.f[k]) && !isDate(t(s.f[k])));
    if (bad.length) { this.setState({ err: `날짜는 YYYY-MM-DD 로 적어 주세요 · ${bad.map((k) => DATES[k]).join(', ')}`, ok: '' }); return; }
    const now = toServer(s);
    const was = this._snap;
    const b = changed(now.body, was.body);
    const p = changed(now.pi, was.pi);
    const pr = changed(now.profile, was.profile);
    if ('name' in b && !now.body.name) { this.setState({ err: '성명은 비울 수 없어요.', ok: '' }); return; }
    if (!Object.keys(b).length && !Object.keys(p).length && !Object.keys(pr).length) {
      this.setState({ err: '', ok: '바뀐 칸이 없어요.' });
      return;
    }
    this.setState({ busy: true, err: '', ok: '' });
    const done = [];
    try {
      if (Object.keys(b).length) {
        const { name, ...rest } = b;
        const patch = { ...rest };
        if (name !== undefined) { patch.title = `${alias(now.body.name)} 어르신`; patch.child_alias = alias(now.body.name); }
        await cases.update(caseId, patch);
        was.body = now.body;
        done.push('사례');
      }
      if (Object.keys(p).length) {
        const old = this._pi || {};
        const oldFam = old.family_members || [];
        const family = now.pi.family_members.map((m, i) => ({ religion: null, education: null, job: null, ...(oldFam[i] || {}), ...m }));
        const saved = await cases.putPersonalInfo(caseId, {
          child_name: now.pi.child_name,
          child_birth_date: now.pi.child_birth_date,
          target_person: now.pi.target_person,
          interviewee: old.interviewee || null,
          family_members: family,
          // 건강 상태 표는 이 화면에서 바꿨을 때만 새로 만든다(아니면 저장돼 있던 그대로).
          health: 'health' in p ? now.pi.health : old.health || null,
        });
        this._pi = saved;
        was.pi = now.pi;
        done.push('개인정보');
      }
      if (Object.keys(pr).length) {
        await senior.updateProfile(caseId, pr);
        was.profile = now.profile;
        done.push('기본정보');
      }
    } catch (e) {
      const part = done.length ? `${done.join(' · ')} 는 저장했어요. 나머지는 못 했어요 — '확정' 을 다시 누르면 남은 것만 다시 저장합니다. ` : '';
      this.setState({ busy: false, err: `${part}(${(e && e.message) || '저장하지 못했어요. 잠시 뒤 다시 해 주세요.'})` });
      return;
    }
    this.setState({ busy: false, ok: `저장했어요 · ${hm(new Date())}` });
  }

  renderValsBase() {
    this.fill();
    const base = super.renderValsBase();
    const s = this.state;
    const { data, caseId, shell, loadErr } = this.props;
    const d = data || {};
    const c = d.c;
    const name = (this._pi && this._pi.child_name) || (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;
    const nv = d.row && d.row.next_visit;
    const go = (k) => this.setState({ tab: k });
    const tabs = (base.tabs || []).map((tb, i) => ({ ...tb, go: () => go(i === 0 ? 'A' : 'B') }));
    const bind = (k) => (e) => { const v = e.target.value; this.setState({ x: { ...this.state.x, [k]: v }, ok: '' }); };
    const x = {};
    const xs = {};
    X_KEYS.forEach((k) => { x[k] = s.x[k] || ''; xs[k] = bind(k); });
    const setRow = (i, k) => (e) => { const v = e.target.value; const n = this.state.fr.slice(); n[i] = { ...n[i], [k]: v }; this.setState({ fr: n, ok: '' }); };
    const famRows = s.fr.map((r, i) => ({
      name: r.name || '', rel: r.rel || '', age: r.age || '', live: r.live || '',
      setName: setRow(i, 'name'), setRel: setRow(i, 'rel'), setAge: setRow(i, 'age'), setLive: setRow(i, 'live'),
    }));
    const masked = name === DASH ? DASH : maskNames(name, [name]);
    return {
      ...base,
      ...shell,
      ...caseLinks(caseId),
      cntApp: '',
      cntFollow: '',
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, d.profile),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${nv ? visitWhen(nv.date, nv.time) : DASH}`,
      docsHref: href('CaseDocs', { caseId }),
      formNote: `S-01 · 등록 ${c ? ymd(c.created_at) : DASH}`,
      cpEx: `예) ${masked}`,
      x,
      xs,
      famRows,
      addRow: () => this.setState({ fr: this.state.fr.concat([{}]) }),
      tabs,
      goB: () => go(s.tab === 'A' ? 'B' : 'A'),
      showMiss: false,
      counselor: (c && c.counselor_name) || '',
      err: loadErr || s.err,
      ok: s.ok,
      saveLabel: s.busy ? '저장 중…' : '확정',
      saveDone: () => this.save(),
      draftSave: () => this.setState({ err: '', ok: "임시 저장은 아직 지원하지 않아요 — '확정' 을 누르면 바뀐 칸이 저장돼요." }),
    };
  }
}

export default function CaseIntake(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, ov] = await Promise.all([cases.get(caseId), soft(senior.profile(caseId)), soft(senior.overview())]);
    const row = ov ? ov.rows.find((r) => r.case_id === caseId) : null;
    return { c, profile, row };
  }, [shell.ready, caseId]);
  // 실명 · 생년월일 · 가족 · 건강: 열람 기록이 남으니 사례가 바뀔 때만 한 번 부른다(저장한 뒤에도 다시 부르지 않는다).
  const personal = useAsync(() => (shell.ready && caseId ? cases.getPersonalInfo(caseId) : null), [shell.ready, caseId]);
  let loadErr = '';
  if (!caseId) loadErr = '대상자를 고르지 않았어요. 대상자 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '사례 정보를 불러오지 못했어요.';
  else if (personal.error) loadErr = personal.error.message || '개인정보를 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, shell, caseId, data: main.loading ? null : main.data, pi: personal.loading ? null : personal.data, loadErr });
  return <View v={v} />;
}
