// 지난 안부 기록 — 디자인 ChildLinkHistory.dc.html. ?case=<id>(사례 상세 '안부 연계' 탭에서 오면 &sec=app).
// 고령자 안부 앱은 아직 없다(아동 앱 콩콩 API 는 아동 사례만 받으니 쓰지 않는다).
//  - 머리(이름 · 사례 번호 · 나이 · 성별 · 가구형태)는 실제 사례(별칭, 실명 열람 기록을 남기지 않는다).
//  - 기간(1 · 2 · 4주) · 보기(문항별 · 날짜별) 단추와 날짜 줄은 오늘 기준 실제 날짜로 그리고,
//    문항 · 답 · 남기신 말씀은 안부 앱 내용이라 '—' / '준비 중' 한 줄만 둔다(무응답으로 보이지 않게 '이 날은 응답이 없었어요' 는 쓰지 않는다).
import { useDC } from '../dc';
import DesignLogic from '../design/ChildLinkHistory.logic';
import { cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH } from '../data/format';
import { subLine } from './CaseInfo.parts';
import View from './ChildLinkHistory.view';

const DOW = ['일', '월', '화', '수', '목', '금', '토'];
const ALLD = 28;
const pad = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const soft = (p) => p.catch(() => null);
const PREP = '고령자 안부 앱 준비 중 — 연결되면 문항과 어르신 답이 여기에 보여요';

function lastDays() {
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const out = [];
  for (let i = 0; i < ALLD; i++) {
    const d = new Date(end);
    d.setDate(end.getDate() - i);
    out.push(d);
  }
  return out;
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, per: 14, view: 'q', day: iso(new Date()), cid: null };
  }

  // 디자인은 저장소(ispot-senior)에서 예시 사례 번호를 읽어 바꾼다 — 실제 화면은 ?case= 만 본다.
  componentDidMountBase() {}

  seniorSync() {}

  renderValsBase() {
    const s = this.state;
    const { data, caseId, fromApp } = this.props;
    const d = data || {};
    const c = d.c;
    const name = (c && c.child_alias) || DASH;
    const k = {
      name,
      short: name === DASH ? DASH : `${name} 님`,
      short0: name === DASH ? '' : name.slice(0, 1),
      age: c ? subLine(c, d.profile) : DASH,
      id: (c && c.case_number) || DASH,
      home: fromApp ? '#/CaseList' : '#/ChildLink',
      homeLabel: fromApp ? '대상자 관리' : '안부 연계',
      back: fromApp ? href('CaseApp', { caseId }) : href('ChildLinkDetail', { caseId }),
    };
    const dates = lastDays();
    const shown = dates.slice(0, s.per);
    const cols = shown.map((x) => ({ md: `${x.getMonth() + 1}/${x.getDate()}`, dow: DOW[x.getDay()] }));
    const rows = [{ id: DASH, q: PREP, cells: shown.map(() => ({ v: DASH, cls: 'miss' })) }];
    const dayIdx = Math.max(0, dates.findIndex((x) => iso(x) === s.day));
    const dd = dates[dayIdx];
    const day = {
      label: `${dd.getMonth() + 1}월 ${dd.getDate()}일 (${DOW[dd.getDay()]})`,
      time: '',
      items: [{ id: DASH, q: PREP, v: DASH, prev: DASH, changed: false, fw: 500, bg: 'transparent' }],
      has: true,
      none: false,
      hasQuote: false,
      quote: '',
      quoteAt: '',
    };
    const dateList = shown.map((x) => {
      const key = iso(x);
      const on = key === s.day;
      return { label: `${x.getMonth() + 1}/${x.getDate()} (${DOW[x.getDay()]})`, meta: DASH, cls: on ? 'on' : '', on: on ? 'true' : 'false', pick: () => this.setState({ day: key }) };
    });
    const periods = [[7, '최근 1주'], [14, '최근 2주'], [28, '최근 4주']].map(([n, label]) => ({
      label, cls: s.per === n ? 'on' : '', on: s.per === n ? 'true' : 'false', pick: () => this.setState({ per: n }),
    }));
    const views = [['q', '문항별'], ['d', '날짜별']].map(([key, label]) => ({
      label, cls: s.view === key ? 'on' : '', on: s.view === key ? 'true' : 'false', pick: () => this.setState({ view: key }),
    }));
    return {
      ...this.props.shell,
      cntApp: '',
      cntFollow: '',
      k,
      cols,
      rows,
      periods,
      views,
      byQ: s.view === 'q',
      byD: s.view === 'd',
      dates: dateList,
      day,
      answered: DASH,
      days: s.per,
      daysTail: '일 · 안부 앱 준비 중',
    };
  }
}

export default function ChildLinkHistory(props) {
  const shell = useShell();
  const { caseId, sec } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile] = await Promise.all([cases.get(caseId), soft(senior.profile(caseId))]);
    return { c, profile };
  }, [shell.ready, caseId]);
  const v = useDC(Logic, { ...props, shell, caseId, fromApp: sec === 'app', data: main.data });
  return <View v={v} />;
}
