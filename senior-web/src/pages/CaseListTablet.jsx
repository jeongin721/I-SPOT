// 대상자 관리(태블릿) — 디자인 CaseListTablet.dc.html. 데이터는 데스크톱 CaseList.jsx 와 같다(고령자 사례 subject_type SENIOR).
//  - 태블릿 디자인에는 쪽 넘김이 없어 한 번에 100건(서버 한 쪽 최대)까지 받아 보인다. 위 '담당 사례 N건' 은 서버 전체 건수.
//  - 이름은 별칭(태블릿 디자인에 실명 보기 단추가 없다). 접수일: 신고접수일, 없으면 등록일.
//  - 위기도: 고령자에는 위기도 판정이 없어 서버 값이 없으면 '—'.
//  - 정렬 단추(전체 · 접수일 · 위기도)는 서버 정렬, 검색은 서버 검색(성함 · 사례 ID).
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/CaseListTablet.logic';
import { cases } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH, age } from '../data/format';
import View from './CaseListTablet.view';

const PER = 100;
const RISK = { HIGH: ['위기', 'chip c-hi'], MEDIUM: ['집중', 'chip c-hi'], LOW: ['관심', 'chip c-mid'], NONE: ['일반', 'chip c-lo'] };

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const { list, query, setQuery, shell } = this.props;
    const items = list.data ? list.data.items : [];
    const rows = items.map((c) => {
      const name = c.child_alias || DASH;
      const risk = c.risk_level ? RISK[c.risk_level] : null;
      const a = age(c.child_birth_year);
      return {
        id: c.case_number,
        ini: name.slice(0, 1),
        name,
        age: a !== null ? `만 ${a}세` : '',
        date: c.report_date || (c.created_at || '').slice(0, 10),
        risk: risk ? risk[0] : DASH,
        cls: risk ? risk[1] : 'chip c-lo',
        href: href('CaseInfo', { caseId: c.id }),
      };
    });
    const arrow = (k) => (k !== 'none' && query.sort === k ? (query.dir === 'up' ? ' ↑' : ' ↓') : '');
    const press = (k) => () => {
      if (k === 'none') setQuery({ ...query, sort: 'none', dir: 'up' });
      else if (query.sort !== k) setQuery({ ...query, sort: k, dir: 'up' });
      else setQuery({ ...query, dir: query.dir === 'up' ? 'down' : 'up' });
    };
    const filters = [['none', '전체'], ['date', '접수일'], ['risk', '위기도']].map(([k, label]) => ({
      label: label + arrow(k), cls: query.sort === k ? 'on' : '', pressed: query.sort === k ? 'true' : 'false', pick: press(k),
    }));
    return {
      ...base, ...shell, rows, filters,
      totalCount: list.data ? list.data.meta.total : DASH,
      search: query.search || '',
      setSearch: (e) => setQuery({ ...query, search: e.target.value }),
      navLinkCnt: '', navFollowCnt: '',
    };
  }
}

export default function CaseListTablet(props) {
  const shell = useShell();
  const [query, setQuery] = useState({ sort: 'none', dir: 'up', search: '' });
  const list = useAsync(() => {
    if (!shell.ready) return null;
    const sort = query.sort === 'date' ? 'report_date' : query.sort === 'risk' ? 'risk' : undefined;
    return cases.list({
      subject_type: 'SENIOR', page: 1, page_size: PER, search: query.search || undefined,
      sort, order: sort ? (query.dir === 'up' ? 'desc' : 'asc') : undefined,
    });
  }, [shell.ready, query.sort, query.dir, query.search]);
  const v = useDC(Logic, { ...props, list, query, setQuery, shell });
  return <View v={v} />;
}
