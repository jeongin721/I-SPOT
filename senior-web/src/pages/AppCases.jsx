// 상담사 앱(폰) · 대상자 목록 — 디자인 AppCases.dc.html.
//  - 목록: 내 진행 중 고령자 사례(App.parts). 이름은 별칭, '만 82세 · 여 · 독거'(가구형태는 senior-profile), 접수일은 report_date(없으면 등록일).
//  - 위기도: 고령자에는 위기도 판정이 없다(학대 분석 대신 생활 · 정서 변화). 칩은 디자인대로 두고 '—'.
//  - 다음 상담: 오늘부터 4주 안 일정 중 그 대상자의 가장 가까운 상담(GET /schedule/events). '이번 주 상담' 은 다음 상담이 이번 주(월~일)인 대상자.
//  - 찾기: 이름 · 사례 ID 에 들어 있으면(이 폰에서 거름).
//  - 사례 요약 창: 메모는 내 메모 중 그 대상자에 붙은 것(GET /memos). 다음 상담 준비 · 녹음 시작 · 자료 올리기 · 이전 상담은
//    그 대상자를 ?case= 로 실어 간다. 다음 상담 준비는 서버가 그때그때 만들어(senior-brief) 늘 볼 수 있다.
import { useDC } from '../dc';
import DesignLogic from '../design/AppCases.logic';
import { memos } from '@cw/api/endpoints';
import { useAppSchedule } from '@cw/data/useAppSchedule';
import { senior, LIVING_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { href } from '../data/nav';
import { DASH } from '../data/format';
import { useAppData, withApp, nameOf, ageLine, consultWhen, upcoming, whenText, msOf, dayKey, addDays, mondayOf } from './App.parts';
import View from './AppCases.view';

const soft = (p) => p.catch(() => null);

class Logic extends withApp(DesignLogic) {
  renderVals() {
    const v = super.renderVals();
    const s = this.state;
    const { app, sched, profiles, memoList } = this.props;
    const mon = mondayOf(new Date());
    const sun = dayKey(addDays(mon, 6));
    const nextOf = {};
    sched.items
      .filter((e) => e.kind === 'CONSULT' && e.case_id && upcoming(e))
      .forEach((e) => {
        if (!nextOf[e.case_id]) nextOf[e.case_id] = e;
      });
    const prof = profiles || {};
    const D = app.elders.map((c) => {
      const p = prof[c.id];
      const nx = nextOf[c.id];
      return {
        c,
        name: nameOf(c),
        no: c.case_number || DASH,
        age: ageLine(c, p && p.living_arrangement ? LIVING_LABELS[p.living_arrangement] : DASH),
        date: c.report_date || (c.created_at || '').slice(0, 10) || DASH,
        next: nx ? consultWhen(nx) : '',
        wk: !!nx && nx.date <= sun,
      };
    });
    const q = (s.q || '').trim();
    const list = D.filter((r) => (s.f === 'wk' ? r.wk : true) && (!q || r.name.includes(q) || r.no.toLowerCase().includes(q.toLowerCase())));
    const cur = s.open ? D.find((r) => r.c.id === s.open) : null;
    const myM = cur ? (memoList || []).filter((m) => m.case_id === cur.c.id) : [];
    const memo = myM.length
      ? myM.map((m) => `${m.unreadable ? '지금은 읽을 수 없어요' : m.text} (${whenText(msOf(m.created_at))})`).join('\n\n')
      : '-';
    const caseId = cur ? cur.c.id : null;
    return {
      ...v,
      total: app.eldersLoading ? DASH : String(D.length),
      countLabel: app.eldersLoading ? '불러오는 중' : `${list.length}명`,
      noRows: !app.eldersLoading && list.length === 0,
      rows: list.map((r) => ({
        id: r.no, name: r.name, age: r.age, date: r.date, rk: DASH, rkCls: 'chip',
        next: r.next ? `다음 상담 ${r.next}` : '예정된 상담 없음', nextCls: r.next ? 'cs-next' : 'cs-next none',
        aria: `${r.name} 사례 요약 보기`, open: () => this.setState({ open: r.c.id }),
      })),
      shOpen: !!cur,
      v: cur
        ? {
            name: `${cur.name} · ${cur.age}`, rk: DASH, rkCls: 'chip', brief: true, noBrief: false,
            kv: [['사례 ID', cur.no], ['접수일', cur.date], ['다음 상담', cur.next || '예정 없음'], ['메모', memo]].map(([k, val]) => ({ k, v: val, cls: k === '메모' ? 'kv-memo' : '' })),
            toBrief: () => this.stSet('ispot-app-from', '#/AppCases'),
            hist: () => {},
            rec: () => {},
            nextHref: href('AppNext', { caseId }),
            recHref: href('AppRecord', { caseId }),
            upHref: href('AppUpload', { caseId }),
            histHref: href('AppHistory', { caseId }),
          }
        : {},
      loadErr: app.eldersErr || sched.error || '',
    };
  }
}

export default function AppCases(props) {
  const app = useAppData();
  const t0 = new Date();
  const sched = useAppSchedule(!!app.userId, dayKey(t0), dayKey(addDays(t0, 28)));
  const ids = app.elders.map((c) => c.id).join(',');
  // 가구형태(독거 · 부부 등)는 대상자마다 senior-profile 에 있다. 못 읽으면 '—'.
  const profiles = useAsync(async () => {
    if (!ids) return {};
    const rows = await Promise.all(app.elders.map((c) => soft(senior.profile(c.id))));
    return Object.fromEntries(app.elders.map((c, i) => [c.id, rows[i]]));
  }, [ids]);
  const memoList = useAsync(() => (app.userId ? memos.list({ page: 1, page_size: 100 }).then((p) => p.items) : null), [app.userId]);
  const v = useDC(Logic, { ...props, app, sched, profiles: profiles.data, memoList: memoList.data });
  return <View v={v} />;
}
