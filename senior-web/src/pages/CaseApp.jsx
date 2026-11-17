// 사례 상세 · 안부 연계 탭 — 디자인 CaseApp.dc.html. ?case=<id>.
// 고령자 안부 앱은 아직 없다(아동 앱 콩콩 API 는 아동 사례만 받으니 쓰지 않는다).
//  - 머리(이름 · 나이 · 성별 · 가구형태 · 사례 번호 · 다음 상담)는 실제 사례: cases.get · senior-profile · senior-overview(다음 방문).
//    이름은 별칭(이 탭에서는 실명 열람 기록을 남기지 않는다). 고령자에는 위기도 판정이 없어 칩은 '위기도 —'.
//  - 안부 질문과 답 · 어르신이 남긴 말씀 · 가족 관찰 메모 · 확인할 답변 · 추가 안부 질문은 안부 앱 내용이라 '준비 중' 한 줄만.
import { useDC } from '../dc';
import DesignLogic from '../design/CaseApp.logic';
import { cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH } from '../data/format';
import { caseLinks, subLine, visitWhen } from './CaseInfo.parts';
import { appPlaceholders } from './ChildLink.parts';
import View from './CaseApp.view';

const soft = (p) => p.catch(() => null);

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const { data, caseId, shell } = this.props;
    const d = data || {};
    const c = d.c;
    const name = (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;
    const nv = d.row && d.row.next_visit;
    return {
      ...base,
      ...shell,
      ...caseLinks(caseId),
      cntApp: '',
      cntFollow: '',
      ...appPlaceholders(c, d.profile, d.row),
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, d.profile),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${nv ? visitWhen(nv.date, nv.time) : DASH}`,
      docsHref: href('CaseDocs', { caseId }),
      appHref: href('CaseApp', { caseId }),
      histHref: href('ChildLinkHistory', { caseId, sec: 'app' }),
    };
  }
}

export default function CaseApp(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, ov] = await Promise.all([cases.get(caseId), soft(senior.profile(caseId)), soft(senior.overview())]);
    const row = ov ? ov.rows.find((r) => r.case_id === caseId) : null;
    return { c, profile, row };
  }, [shell.ready, caseId]);
  const v = useDC(Logic, { ...props, shell, caseId, data: main.data });
  return <View v={v} />;
}
