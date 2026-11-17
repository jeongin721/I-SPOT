// 안부 연계 묶음(ChildLink · ChildLinkDetail · ChildLinkHistory · CaseApp)이 같이 쓰는 작은 변환들.
// 고령자 안부 앱이 아직 없어 안부 앱 내용(응답 · 말씀 · 가족 메모 · 추가 질문)은 '—' / '준비 중' 으로 채운다.
import { DASH } from '../data/format';
import { subLine, visitWhen, visitType } from './CaseInfo.parts';

/** 안부 앱이 없을 때 머리 · 목록 칸(CaseApp 도 같은 모양을 쓴다). */
export function appPlaceholders(c, profile, row, extra = {}) {
  const name = (c && c.child_alias) || DASH;
  const nv = row && row.next_visit;
  return {
    k: {
      name,
      short: name === DASH ? DASH : `${name} 님`,
      ini: name === DASH ? '' : name.slice(0, 1),
      age: c ? subLine(c, profile) : DASH,
      types: DASH,
      id: (c && c.case_number) || DASH,
      reason: '안부 앱 준비 중',
      rCls: 'chip c-normal',
      last: DASH,
      count: DASH,
      next: nv ? `${visitWhen(nv.date, nv.time)} ${visitType(nv.consult_type)}` : DASH,
      urgent: false,
      app: '어르신 안부 앱 준비 중',
      quote: '',
      quoteAt: '',
      hasQuote: false,
      famConsent: '가족 연계 준비 중',
      famCls: 'chip c-normal',
      famScope: `공유 범위: ${DASH}`,
      ...extra,
    },
    answers: [{
      id: DASH, q: '고령자 안부 앱이 아직 연결되지 않았어요. 연결되면 안부 질문과 어르신 답이 여기에 보여요.', prev: [], ans: DASH, changed: false, fw: 500, bg: 'transparent', flagText: '',
    }],
    famNotes: [{ who: '준비 중', at: DASH, text: '가족 관찰 메모는 안부 앱 가족 연계가 생기면 여기에 보여요.' }],
    flags: [],
    flagCount: 0,
    goAns: () => {},
  };
}
