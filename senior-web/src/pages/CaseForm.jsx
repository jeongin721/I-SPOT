// 사례 상세 · 기관 서식 작성 — 디자인 CaseForm.dc.html. 주소 ?case=<사례 id>.
//  - 서버의 기관 서식(caseForms, API_CONTRACT 22절)은 아동 서식 틀이다(서식 6 안전영역 11문항 · 점검표 9문항 · 가족관계 척도 응답자
//    부 · 모 · 아동 · 사정결과 집중/일반/모니터링). 고령자 서식(S-02 · 점검표 10문항 · SGDS-K · 자살위험 선별)과 칸이 맞지 않아 쓰지 않는다.
//  - 그래서 화면 틀(서식 탭 · 문항)은 디자인 그대로 두고, 내용 칸은 비운다: 디자인의 AI 제안 · 근거 · 미리 고른 응답 · AI 초안 글은 넣지 않는다.
//    문항을 눌러 볼 수는 있지만 저장되지 않는다 — '임시 저장' · '확정' 은 '준비 중' 안내만, 화면 위에 준비 중 줄을 둔다.
//  - 머리(이름 · 나이 · 다음 상담)와 점검표 머리(성명 · 담당 상담사 · 출생연도)는 사례 값. 점검일 · 이전 점검일 · 점검장소는 기록이 없어 '—' · 빈칸.
//  - 이름은 별칭(실명 열람 기록은 탭1 에서만). 고령자에는 위기도 판정이 없어 머리 칩은 '—'.
import { useDC } from '../dc';
import DesignLogic from '../design/CaseForm.logic';
import { cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, age } from '../data/format';
import { caseLinks, subLine, visitWhen } from './CaseInfo.parts';
import View from './CaseForm.view';

const soft = (p) => p.catch(() => null);
const READY = '고령자 기관 서식 저장은 준비 중이에요 · 문항을 눌러 볼 수는 있지만 저장되지 않아요';
const sel = (on) => ({ bg: on ? '#E8F4FC' : 'transparent', fg: on ? '#1F3A56' : '#55687A', fw: on ? 700 : 400, bd: on ? 'inset 0 0 0 1px #1F3A56' : 'none' });

/** 이름 가리기: 김순자 → 김○자, 순자 → 순○ (디자인 nmMask 규칙을 이 사례 이름에). */
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

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    // 디자인이 미리 골라 둔 응답(Key Person '있음' · SGDS-K · 자살위험 선별)은 비운다.
    this.state = { ...this.state, key: '', gd: {}, sr: {}, note: '' };
  }

  names() {
    const c = this.props.data && this.props.data.c;
    return [c && c.child_alias].filter(Boolean);
  }

  nmMask(t) {
    return maskNames(t, this.names());
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { data, caseId, shell, loadErr } = this.props;
    const d = data || {};
    const c = d.c;
    const list = d.sessions || [];
    const latest = list[0] || null;
    const links = caseLinks(caseId, latest && latest.id);
    const name = (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;
    const nv = d.brief && d.brief.next_visit;
    const a = c ? age(c.child_birth_year) : null;

    // S-02: AI 제안 · 근거 없이, 상담사가 고른 값만.
    let idx = 0;
    const safety = (base.safety || []).map((g) => ({
      ...g,
      items: g.items.map((it) => {
        const k = idx++;
        const cur = s.sa[k] || '';
        return {
          ...it, ai: '', ev: '', hasEv: false,
          opts: ['높음', '보통', '낮음'].map((o) => ({ label: o, ...sel(cur === o), pick: () => this.setState({ sa: { ...this.state.sa, [k]: cur === o ? '' : o } }) })),
        };
      }),
    }));
    // 점검표: 미리 고른 응답 없이.
    const checks = (base.checks || []).map((it, i) => {
      const cur = s.ck[i] || '';
      return {
        ...it, ai: '', ev: '', hasEv: false,
        opts: ['예', '아니오'].map((o) => ({ label: o, ...sel(cur === o), pick: () => this.setState({ ck: { ...this.state.ck, [i]: cur === o ? '' : o } }) })),
      };
    });
    // 위기도 평가표: AI 제안 점수 · 근거 없이, 합계도 상담사가 고른 값으로만.
    const LBL = ['매우 아니다', '아니다', '그렇다', '매우 그렇다'];
    let rs = 0;
    let ps = 0;
    let filled = 0;
    const scale = (base.scale || []).map((it) => {
      const n = it.n;
      const v = s.sc[n] !== undefined && s.sc[n] !== '' ? s.sc[n] : null;
      if (v !== null) {
        filled++;
        if (n <= 21) rs += v;
        else ps += v;
      }
      return {
        ...it, ev: '',
        opts: [0, 1, 2, 3].map((o) => ({ label: LBL[o], ...sel(v === o), pick: () => this.setState({ sc: { ...this.state.sc, [n]: v === o ? '' : o } }) })),
      };
    });
    // 자살위험 선별: 응답이 하나도 없으면 결과 · 안내를 쓰지 않는다('위기 신호 확인되지 않음' 으로 보이지 않게).
    const none = !base.srN;
    const ready = () => this.setState({ note: READY });

    return {
      ...base,
      ...shell,
      ...links,
      docsHref: href('CaseDocs', { caseId }),
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, d.profile),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${nv ? visitWhen(nv.date, nv.time) : DASH}`,
      safety,
      checks,
      scale,
      riskSum: rs,
      protSum: ps,
      filled,
      srLevel: none ? DASH : base.srLevel,
      srGuide: none ? DASH : base.srGuide,
      keyAi: 'AI 제안 · 준비 중',
      keyEv: '',
      draftChip: 'AI 초안 · 준비 중',
      ckOpinion: '',
      ckPlan: '',
      fhName: name,
      fhCounselor: (c && c.counselor_name) || DASH,
      fhBirth: c && c.child_birth_year ? `${c.child_birth_year}년생${a !== null ? ` (만 ${a}세)` : ''}` : DASH,
      fhDate: DASH,
      fhPlace: '',
      fhPrev: DASH,
      maskEx: `예) ${name !== DASH ? maskNames(name, [name]) : DASH}`,
      formNote: loadErr || s.note || READY,
      saveDraft: ready,
      saveDone: ready,
    };
  }

  renderVals() {
    return { ...super.renderVals(), navLinkCnt: '', navFollowCnt: '' };
  }
}

export default function CaseForm(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, page, brief] = await Promise.all([
      cases.get(caseId),
      soft(senior.profile(caseId)),
      soft(cases.listSessions(caseId, { page_size: 100 })),
      soft(senior.brief(caseId)),
    ]);
    const sessions = page ? [...page.items].sort((x, y) => y.session_number - x.session_number) : [];
    return { c, profile, sessions, brief };
  }, [shell.ready, caseId]);
  let loadErr = '';
  if (!caseId) loadErr = '대상자를 고르지 않았어요. 대상자 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '대상자 정보를 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, shell, caseId, data: main.data, loadErr });
  return <View v={v} />;
}
