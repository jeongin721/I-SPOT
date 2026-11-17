// 안부 연계(목록) — 디자인 ChildLink.dc.html.
// 고령자 안부 앱은 아직 없다(아동 앱 콩콩 API 는 아동 사례만 받으니 쓰지 않는다).
//  - 어르신 목록 · 이름(별칭) · 나이 · 성별 · 사례 번호는 실제 고령자 사례(GET /cases subject_type SENIOR).
//  - 최근 3주 응답 · 마지막 응답 · 상태 · 가족 연결 같은 안부 앱 내용은 전부 '—' / '준비 중'.
//  - 위쪽 긴급 · 무응답 알림 띠는 디자인대로 두되, 예시 사연 대신 '안부 앱 준비 중' 안내로 바꾼다.
//  - '확인할 어르신' 은 안부 앱 신호가 없어 0명 — 처음엔 '전체' 를 보여 준다.
import { useDC } from '../dc';
import DesignLogic from '../design/ChildLink.logic';
import { cases } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH, age, genderLabel } from '../data/format';
import View from './ChildLink.view';

const SOON = '#/Soon?name=' + encodeURIComponent('어르신 안부 앱');

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, f: 'all', q: '' };
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { list, shell } = this.props;
    const items = (list.data && list.data.items) || [];
    const q = s.q.trim();
    const shown = s.f === 'need' ? [] : items.filter((c) => !q || (c.child_alias || '').includes(q) || (c.case_number || '').includes(q));
    const rows = shown.map((c) => {
      const name = c.child_alias || DASH;
      const a = age(c.child_birth_year);
      return {
        name,
        ini: name.slice(0, 1),
        age: [a !== null ? `만 ${a}세` : null, genderLabel(c.child_gender)].filter((x) => x && x !== DASH).join(' · '),
        id: c.case_number || DASH,
        href: href('ChildLinkDetail', { caseId: c.id }),
        count: DASH,
        last: DASH,
        reason: '준비 중',
        rCls: 'chip c-normal',
        fam: DASH,
        famCls: 'chip c-normal',
      };
    });
    const total = list.data ? list.data.meta.total : null;
    const filters = [['need', '확인할 어르신 0'], ['all', `전체 ${total ?? DASH}`]].map(([k, label]) => ({
      label, cls: s.f === k ? 'on' : '', pick: () => this.setState({ f: k }),
    }));
    return {
      ...base,
      ...shell,
      cntApp: '',
      cntFollow: '',
      rows,
      filters,
      search: s.q,
      setSearch: (e) => this.setState({ q: e.target.value }),
      alertHref: SOON,
      alertName: '안부 앱 준비 중',
      alertText: ' · 고령자 안부 앱이 아직 연결되지 않아 긴급 표현 알림이 오지 않아요. 연결되면 여기에 보여요.',
      silentName: '안부 앱 준비 중',
      silentText: ' · 안부 응답이 아직 없어 무응답 알림도 없어요. 연결되면 48시간 이상 무응답인 어르신이 여기에 보여요.',
    };
  }
}

export default function ChildLink(props) {
  const shell = useShell();
  // 고령자 사례 전부(한 쪽 100건). 검색은 받아 온 목록 안에서 이름(별칭) · 사례 번호로 거른다.
  const list = useAsync(() => (shell.ready ? cases.list({ subject_type: 'SENIOR', page_size: 100 }) : null), [shell.ready]);
  const v = useDC(Logic, { ...props, list, shell });
  return <View v={v} />;
}
