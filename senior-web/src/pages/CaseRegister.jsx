// 새 사례 등록 · 초기상담지(시니어용) — 디자인 CaseRegister.dc.html.
// '등록' 을 누르면:
//  1) POST /cases — subject_type 'SENIOR'. 칸 이름은 아동과 같다: child_alias = 성명을 가린 별칭(김순자 → 김○자),
//     child_birth_year · child_gender = 어르신 출생연도 · 성별. personal_info(암호화 저장) = 실명 · 생년월일 ·
//     주 돌봄자(target_person: 이름 · 관계 · 생년월일) · 가족관계 표(성명 · 관계 · 나이 · 동거여부) · 건강 상태 표(health).
//     report_date = 상담 접수일, linked_date = 의뢰일, first_interview_date = 초기상담일, case_number = 사례번호(비우면 서버가 만듦).
//     초기상담 글 칸: intake_problem = 주호소, linked_background = 의뢰 경로 · 의뢰인, intake_guardian_relation = 주 돌봄자 · 가족과의 관계,
//     notes = 주호소 상세 · 생활력, intake_attitude = 어르신 태도 · 정서 상태, intake_environment = 주거 환경, intake_opinion = 상담사 소견.
//  2) PATCH /cases/{id}/senior-profile — 가구형태(living_arrangement, 세부는 care_notes), 장기요양등급(care_grade),
//     주요 질환 · 장애(health_notes), 복용 약(takes_medication · medication_notes), 최근 낙상(care_notes),
//     일상생활 도움 필요 활동(care_needs · care_needs_note).
//  3) CaseInfo?case= 로 간다. 2) 가 실패하면 사례는 이미 있으니 다시 누르면 2) 만 다시 한다.
// 서버에 칸이 없어 입력만 받고 저장하지 않는 것: 주 상담 영역 · 위기도(초기 판단, 고령자는 위기도 판정 없음) · 연락처 · 주소 · 비상연락 가족 ·
//  상담 동의 · 대리 동의 사유 · 가족 정보 공유 범위 · 녹음 동의 · 공유 범위 메모 · 의사소통 고려사항(청력 · 시력 · 큰 글씨 · 말 속도 · 호칭) ·
//  주요 어려움 · 정서 · 위기 신호 고르기 · 가족관계 표의 연락처 · 거주지 · 연락 빈도 · 사회관계 · 경제 · 이용 중인 서비스.
//  담당 상담사 칸은 로그인한 사람(요청자가 담당이 된다, 읽기만).
import { useNavigate } from 'react-router-dom';
import { useDC } from '../dc';
import DesignLogic from '../design/CaseRegister.logic';
import { cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import View from './CaseRegister.view';

const pad = (n) => String(n).padStart(2, '0');
const today = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const isDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(new Date(v).getTime());
const t = (v) => String(v || '').trim();
const orNull = (v) => t(v) || null;
const picked = (v) => (t(v) && v !== '선택' ? t(v) : '');

// 필수(디자인 그대로, 단 사례번호는 비우면 서버가 만든다).
const NAMES = { report: '상담 접수일', link: '의뢰일', name: '성명', sex: '성별', birth: '생년월일', target: '주 돌봄자', rel: '관계', m1: '의뢰 경로', m2: '주 상담 영역', how: '주호소', consent: '상담 동의', share: '가족 정보 공유 범위' };
const DATES = { report: '상담 접수일', link: '의뢰일', first: '초기상담일', birth: '생년월일', tbirth: '주 돌봄자 생년월일' };

// 가구형태 → living_arrangement
const LIVING = {
  '독거': 'ALONE', '독거(자녀 인근 거주)': 'ALONE', '부부': 'COUPLE', '자녀동거': 'WITH_FAMILY', '조손': 'WITH_FAMILY',
  '형제 · 친척 동거': 'WITH_FAMILY', '비혈연 동거': 'OTHER', '시설 거주': 'FACILITY', '기타': 'OTHER',
};
const PLAIN_LIVING = { '독거': 1, '부부': 1, '자녀동거': 1 }; // 이 셋만 분류로 충분, 나머지는 care_notes 에 원래 이름을 남긴다
// 일상생활 · 도움이 필요한 활동 → care_needs
const NEEDS = {
  '식사하기': 'MEAL', '식사 준비': 'MEAL', '청소 · 빨래': 'HOUSEWORK', '장보기': 'HOUSEWORK', '실내 이동': 'MOBILITY',
  '계단 오르기': 'MOBILITY', '교통수단 이용': 'MOBILITY', '혼자 외출': 'MOBILITY', '약 챙겨 먹기': 'MEDICATION',
};

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
function ageFrom(birth) {
  if (!isDate(birth)) return null;
  const b = new Date(birth);
  const n = new Date();
  let a = n.getFullYear() - b.getFullYear();
  if (n.getMonth() < b.getMonth() || (n.getMonth() === b.getMonth() && n.getDate() < b.getDate())) a -= 1;
  return a;
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
const join = (arr, sep = ' · ') => arr.filter(Boolean).join(sep);
const cut = (v, n) => (v && v.length > n ? v.slice(0, n) : v);

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    // 디자인 예시 값(접수일 2026-10-12 · 사례번호 C-2026-0352)은 지우고 오늘 날짜 · 빈 사례번호로 시작한다.
    this.state = {
      ...this.state,
      f: { ...this.state.f, report: today(), link: today(), no: '' },
      x: {}, // 디자인에서 값을 받지 않던 칸(저장하는 것만 묶음)
      fr: [{}, {}], // 가족관계 표 줄
      busy: false, err: '', createdId: null,
    };
  }

  miss() {
    const f = this.state.f;
    return Object.keys(NAMES).filter((k) => { const v = t(f[k]); return !v || v === '선택'; });
  }

  payload() {
    const s = this.state;
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
      subject_type: 'SENIOR',
      title: `${alias(name)} 어르신`,
      child_alias: alias(name),
      child_birth_year: Number(f.birth.slice(0, 4)),
      child_gender: f.sex === '여' ? 'F' : f.sex === '남' ? 'M' : null,
      report_date: f.report,
      linked_date: f.link,
      first_interview_date: isDate(f.first) ? f.first : null,
      case_number: t(f.no) || undefined,
      linked_background: cut(join([picked(f.m1) ? `의뢰 경로: ${f.m1}` : '', t(x.referrer) ? `의뢰인: ${t(x.referrer)}` : '']), 2000) || null,
      intake_problem: cut(orNull(f.how), 2000),
      intake_guardian_relation: cut(orNull(x.guardRel), 2000),
      intake_attitude: cut(orNull(x.attitude), 2000),
      intake_environment: cut(orNull(x.env), 2000),
      intake_opinion: cut(orNull(x.opinion), 2000),
      notes: cut(orNull(x.detail), 4000),
      personal_info: {
        child_name: cut(name, 50),
        child_birth_date: f.birth,
        target_person: caregiver ? { name: cut(caregiver, 50), relation: rel, birth_date: isDate(f.tbirth) ? f.tbirth : null } : null,
        interviewee: null,
        family_members: family.slice(0, 30),
        health,
      },
    };

    const fam = s.fam || '';
    const famText = fam ? `${fam}${s.famOther ? `: ${s.famOther}` : ''}` : '';
    const trOn = Object.keys(s.tr || {}).filter((k) => s.tr[k] && k !== '도움 필요 없음');
    const needs = [...new Set(trOn.map((k) => NEEDS[k] || 'OTHER'))];
    const meds = t(x.meds);
    const profile = {
      living_arrangement: fam ? LIVING[fam] || 'OTHER' : null,
      care_grade: careGrade(x.grade),
      health_notes: cut(join([t(x.disName) ? `주요 질환: ${t(x.disName)}` : '', t(x.dsbName) ? `장애: ${t(x.dsbName)}` : '']), 2000) || null,
      takes_medication: meds ? !/^없음/.test(meds) : H.med === '유' ? true : null,
      medication_notes: meds && !/^없음/.test(meds) ? cut(meds, 2000) : null,
      care_notes: cut(join([famText && !PLAIN_LIVING[fam] ? `가구형태: ${famText}` : '', t(x.fall) ? `최근 낙상: ${t(x.fall)}` : ''], '\n'), 2000) || null,
      care_needs: needs,
      care_needs_note: cut(join(trOn.map((k) => (k === '기타' && s.trOther ? `기타: ${s.trOther}` : k))), 2000) || null,
    };
    return { body, profile };
  }

  async submit() {
    const s = this.state;
    if (s.busy) return;
    const miss = this.miss();
    if (miss.length) { this.setState({ tab: 'A', tried: true, err: '' }); return; }
    const bad = Object.keys(DATES).filter((k) => t(s.f[k]) && !isDate(t(s.f[k])));
    if (bad.length) { this.setState({ err: `날짜는 YYYY-MM-DD 로 적어 주세요 · ${bad.map((k) => DATES[k]).join(', ')}` }); return; }
    const { body, profile } = this.payload();
    this.setState({ busy: true, err: '' });
    let id = s.createdId;
    try {
      if (!id) {
        const made = await cases.create(body);
        id = made.id;
        this.setState({ createdId: id });
      }
    } catch (e) {
      this.setState({ busy: false, err: (e && e.message) || '사례를 등록하지 못했어요. 잠시 뒤 다시 해 주세요.' });
      return;
    }
    try {
      await senior.updateProfile(id, profile);
    } catch (e) {
      this.setState({ busy: false, err: `사례는 등록했어요. 기본정보(가구형태 · 복약 · 돌봄 필요) 저장은 못 했어요 — '등록' 을 다시 누르면 기본정보만 다시 저장합니다. (${(e && e.message) || '오류'})` });
      return;
    }
    this.setState({ busy: false });
    this.props.navigate(href('CaseInfo', { caseId: id }).slice(1));
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const miss = this.miss();
    const go = (k) => { if (k === 'B' && miss.length) { this.setState({ tab: 'A', tried: true }); return; } this.setState({ tab: k }); };
    const tabs = (base.tabs || []).map((tb, i) => ({ ...tb, go: () => go(i === 0 ? 'A' : 'B') }));
    const bind = (k) => (e) => { const v = e.target.value; this.setState({ x: { ...this.state.x, [k]: v } }); };
    const X = ['referrer', 'guardRel', 'detail', 'hsName', 'disName', 'dsbName', 'hospN', 'hospY', 'hospM', 'psyName', 'medY', 'medM', 'cnsWhy', 'cnsN', 'cnsY', 'cnsM', 'meds', 'grade', 'fall', 'attitude', 'env', 'opinion'];
    const x = {};
    const xs = {};
    X.forEach((k) => { x[k] = s.x[k] || ''; xs[k] = bind(k); });
    const setRow = (i, k) => (e) => { const v = e.target.value; const n = this.state.fr.slice(); n[i] = { ...n[i], [k]: v }; this.setState({ fr: n }); };
    const famRows = s.fr.map((r, i) => ({
      name: r.name || '', rel: r.rel || '', age: r.age || '', live: r.live || '',
      setName: setRow(i, 'name'), setRel: setRow(i, 'rel'), setAge: setRow(i, 'age'), setLive: setRow(i, 'live'),
    }));
    return {
      ...base, ...this.props.shell, x, xs, famRows,
      addRow: () => this.setState({ fr: this.state.fr.concat([{}]) }),
      tabs, goB: () => go(s.tab === 'A' ? 'B' : 'A'),
      fe: { ...base.fe, no: '' }, fi: { ...base.fi, no: 'false' },
      showMiss: s.tab === 'A' && s.tried && miss.length > 0, missText: miss.map((k) => NAMES[k]).join(', '),
      counselor: this.props.shell.meName || '',
      err: s.err,
      submitLabel: s.busy ? '등록 중…' : '등록',
      submit: (e) => { if (e && e.preventDefault) e.preventDefault(); this.submit(); },
    };
  }
}

export default function CaseRegister(props) {
  const shell = useShell();
  const navigate = useNavigate();
  const v = useDC(Logic, { ...props, shell, navigate });
  return <View v={v} />;
}
