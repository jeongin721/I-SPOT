// 사례 관리(목록) — 디자인 CaseList.dc.html. 고령자 사례(subject_type SENIOR)만 서버 쪽에서 쪽 나눠 받는다.
//  - 이름: 기본은 별칭, '실명 보기' 를 켜면 with_child_name=true 로 다시 받아 실명(서버에 열람 기록이 남는다).
//  - 접수일: 신고접수일(report_date), 없으면 등록일.
//  - 위기도: 고령자에는 위기도 판정이 없다(학대 분석 대신 생활 · 정서 변화). 칸은 디자인대로 두고 서버 판단이 없으면 '—'.
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/CaseList.logic';
import { cases } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH, age } from '../data/format';
import View from './CaseList.view';

const PER = 10;
const RISK = { HIGH: ['위기', 'chip c-hi'], MEDIUM: ['집중', 'chip c-hi'], LOW: ['관심', 'chip c-mid'], NONE: ['일반', 'chip c-lo'] };

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { list, query, setQuery, shell } = this.props;
    const items = list.data ? list.data.items : [];
    const total = list.data ? list.data.meta.total : 0;
    const pages = Math.max(1, Math.ceil(total / PER));
    const pg = query.page;
    const go = (n) => () => setQuery({ ...query, page: Math.min(Math.max(1, n), pages) });
    const bs = Math.floor((pg - 1) / 4) * 4 + 1;
    const be = Math.min(bs + 3, pages);
    const nums = [];
    if (bs > 1) nums.push({ label: '…', cls: 'pg-n pg-gap', go: go(bs - 1), aria: `${bs - 1}쪽`, cur: 'false' });
    for (let n = bs; n <= be; n++) nums.push({ label: String(n), cls: n === pg ? 'pg-n on' : 'pg-n', go: go(n), aria: `${n}쪽`, cur: n === pg ? 'page' : 'false' });
    if (be < pages) nums.push({ label: '…', cls: 'pg-n pg-gap', go: go(be + 1), aria: `${be + 1}쪽`, cur: 'false' });
    const pager = {
      pages: nums, first: go(1), prev: go(pg - 1), next: go(pg + 1), last: go(pages), atStart: pg === 1, atEnd: pg === pages,
      info: total ? `${total}건 중 ${(pg - 1) * PER + 1}–${Math.min(pg * PER, total)}` : list.loading ? '불러오는 중…' : '0건',
    };
    const rows = items.map((c) => {
      const name = (s.real && c.child_name) || c.child_alias || DASH;
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
    // 정렬 단추: 전체(등록 최신순) · 접수일 · 위기도 — 서버 정렬을 쓴다.
    const arrow = (k) => (k !== 'none' && query.sort === k ? (query.dir === 'up' ? ' ↑' : ' ↓') : '');
    const press = (k) => () => {
      if (k === 'none') setQuery({ sort: 'none', dir: 'up', page: 1 });
      else if (query.sort !== k) setQuery({ sort: k, dir: 'up', page: 1 });
      else setQuery({ ...query, dir: query.dir === 'up' ? 'down' : 'up', page: 1 });
    };
    const filters = [['none', '전체'], ['date', '접수일'], ['risk', '위기도']].map(([k, label]) => ({
      label: label + arrow(k), cls: query.sort === k ? 'on' : '', pressed: query.sort === k ? 'true' : 'false', pick: press(k),
    }));
    const setReal = this.props.setReal;
    const toggleReal = () => {
      this.setState({ real: !s.real });
      setReal(!s.real);
    };
    return {
      ...base, ...shell, rows, pager, filters, toggleReal, totalCount: total,
      search: query.search || '',
      setSearch: (e) => setQuery({ ...query, search: e.target.value, page: 1 }),
    };
  }
}

export default function CaseList(props) {
  const shell = useShell();
  const [query, setQuery] = useState({ sort: 'none', dir: 'up', page: 1 });
  const [real, setReal] = useState(false);
  const list = useAsync(() => {
    if (!shell.ready) return null;
    const sort = query.sort === 'date' ? 'report_date' : query.sort === 'risk' ? 'risk' : undefined;
    return cases.list({
      subject_type: 'SENIOR', page: query.page, search: query.search || undefined, page_size: PER, with_child_name: real || undefined,
      sort, order: sort ? (query.dir === 'up' ? 'desc' : 'asc') : undefined,
    });
  }, [shell.ready, query.sort, query.dir, query.page, query.search, real]);
  const v = useDC(Logic, { ...props, list, query, setQuery, setReal, shell });
  return <View v={v} />;
}
