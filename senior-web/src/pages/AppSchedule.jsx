// 상담사 앱(폰) · 일정 — 디자인 AppSchedule.dc.html.
// 서버 연결: 웹 일정과 같은 일정(GET · POST · PATCH · DELETE /schedule/events). 웹에서 넣은 일정이 그대로 보이고, 여기서 넣은 것도 웹에 보인다.
//  - 이번 주 줄 · 펼친 달력: 고른 날이 든 달(그 달을 덮는 주 전부)을 한 번에 받아 점(일정 있음)을 찍는다.
//  - 상담 일정: '어르신 · 상담 유형'. 다음 상담 준비(앱 · 다음 상담 준비) · 녹음 시작(앱 · 녹음)으로 그 대상자를 ?case= 로 싣고 간다.
//    사례가 가려진 상담(담당이 바뀐 사례 등)은 '다음 상담 준비중' 처럼 흐리게.
//  - 개인 · 기관 일정: 제목(없으면 분류 이름). 폰에서 새로 넣으면 분류는 '기타'(웹에서 바꿀 수 있다).
//  - 상담 유형: 서버는 정기 · 초기 · 방문 · 전화 · 종결 다섯 가지라 디자인의 '내방상담' 은 정기상담으로 저장된다(웹 일정과 같다).
//  - 수정 · 삭제는 만든 사람만(editable). 남의 공유 일정은 누르면 안내만.
//  - 날짜 고르기는 디자인처럼 그 주 7일. 다른 주는 달력에서 날을 고른 뒤 추가한다.
//  - 상세의 '다음 상담 준비 준비됨 · 준비 중' 줄은 정할 서버 값이 없어 넣지 않았다(다음 상담 준비는 열 때 서버가 만든다).
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/AppSchedule.logic';
import { schedule } from '@cw/api/endpoints';
import { useAppSchedule } from '@cw/data/useAppSchedule';
import { href } from '../data/nav';
import { DASH } from '../data/format';
import { useAppData, withApp, elderOpts, consultLabel, categoryLabel, dayKey, addDays, mondayOf, parseYmd } from './App.parts';
import View from './AppSchedule.view';

const DOW = ['월', '화', '수', '목', '금', '토', '일'];
const CONSULT_CODE = { 정기상담: 'REGULAR', 방문상담: 'VISIT', 전화상담: 'PHONE', 내방상담: 'REGULAR', 초기상담: 'INITIAL' };
const CONSULT_TEXT = { REGULAR: '정기상담', VISIT: '방문상담', PHONE: '전화상담', INITIAL: '초기상담', CLOSING: '정기상담' };
const dowOf = (d) => DOW[(d.getDay() + 6) % 7];
const label = (d) => `${d.getMonth() + 1}월 ${d.getDate()}일 ${dowOf(d)}요일`;

/** 고른 날이 든 달을 덮는 주(월~일) 전부. */
function monthGrid(day) {
  const d = parseYmd(day);
  const first = new Date(d.getFullYear(), d.getMonth(), 1);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const start = mondayOf(first);
  const end = addDays(mondayOf(last), 6);
  return { start, end, month: d.getMonth(), year: d.getFullYear() };
}

class Logic extends withApp(DesignLogic) {
  constructor(props) {
    super(props);
    const today = dayKey(new Date());
    this.state = { ...this.state, day: today, today, sheet: null, ask: false, f: {}, events: [], busy: false, err: '' };
  }

  renderVals() {
    const base = super.renderVals();
    const s = this.state;
    const { app, sched, setDay } = this.props;
    const stop = (ev) => {
      if (ev && ev.stopPropagation) ev.stopPropagation();
    };
    const items = sched.items;
    const has = (key) => items.some((e) => e.date === key);
    const names = Object.fromEntries(app.elders.map((c) => [c.id, c.child_alias]));
    const titleOf = (e) =>
      e.kind === 'CONSULT' ? `${(e.case_id && names[e.case_id]) || e.child_alias || '어르신'} · ${consultLabel(e.consult_type)}` : e.title || categoryLabel(e.category);
    const pick = (key, extra = {}) => {
      this.setState({ day: key, ...extra });
      setDay(key);
    };

    const sel = parseYmd(s.day);
    const mon = mondayOf(sel);
    const thisMon = dayKey(mondayOf(parseYmd(s.today)));
    const days = DOW.map((dow, k) => {
      const d = addDays(mon, k);
      const key = dayKey(d);
      return {
        dow, n: String(d.getDate()), sel: key === s.day ? 'true' : 'false',
        cls: `day${key === s.day ? ' on' : ''}${key === s.today ? ' today' : ''}`, dot: has(key) ? 'dot' : 'dot no', pick: () => pick(key),
      };
    });
    const g = monthGrid(s.day);
    const cells = [];
    for (let d = g.start; d <= g.end; d = addDays(d, 1)) {
      const key = dayKey(d);
      const any = has(key);
      cells.push({
        n: String(d.getDate()), sel: key === s.day ? 'true' : 'false', aria: `${d.getMonth() + 1}월 ${d.getDate()}일${any ? ' · 일정 있음' : ''}`,
        cls: `mc${d.getMonth() !== g.month ? ' out' : ''}${key === s.day ? ' on' : ''}${key === s.today ? ' today' : ''}`, dot: any ? 'dot' : 'dot no',
        pick: () => pick(key, { exp: false }),
      });
    }

    const evs = items
      .filter((e) => e.date === s.day)
      .map((e) => {
        const isC = e.kind === 'CONSULT';
        const brief = isC && !!e.case_id && !e.case_hidden;
        return {
          time: e.time || '종일', title: titleOf(e), sub: e.place || '장소 미정', tag: isC ? '상담' : '개인 · 기관', chipCls: isC ? 'chip gold' : 'chip',
          isC, brief, noBrief: isC && !brief, aria: `${titleOf(e)} 자세히 보기`,
          open: () => this.setState({ sheet: { mode: 'view', id: e.id }, ask: false, err: '' }), stop,
          toBrief: (ev) => {
            stop(ev);
            this.stSet('ispot-app-from', '#/AppSchedule');
          },
          rec: stop,
          nextHref: brief ? href('AppNext', { caseId: e.case_id }) : undefined,
          recHref: brief ? href('AppRecord', { caseId: e.case_id }) : href('AppRecord'),
        };
      });

    const cur = s.sheet && s.sheet.id ? items.find((e) => e.id === s.sheet.id) : null;
    const notMine = () => this.setState({ err: '다른 사람이 만든 공유 일정은 고치거나 지울 수 없어요.' });
    const v = cur
      ? {
          title: titleOf(cur), tag: cur.kind === 'CONSULT' ? '상담' : '개인 · 기관', chipCls: cur.kind === 'CONSULT' ? 'chip gold' : 'chip',
          rows: [['날짜', label(parseYmd(cur.date))], ['시간', cur.time || '종일'], ['장소', cur.place || DASH]].map(([k, val]) => ({ k, v: val })),
          edit: () =>
            cur.editable
              ? this.setState({
                  sheet: { mode: 'form', id: cur.id }, err: '',
                  f: {
                    t: cur.kind === 'CONSULT' ? 'c' : 'p', elder: cur.case_id || '', ctype: CONSULT_TEXT[cur.consult_type] || '정기상담',
                    title: cur.title || '', day: cur.date, time: cur.time || '', place: cur.place || '',
                  },
                })
              : notMine(),
          askDel: () => (cur.editable ? this.setState({ ask: true }) : notMine()),
          cancelDel: () => this.setState({ ask: false }),
          del: () => this.run(() => schedule.remove(cur.id), { sheet: null, ask: false }, '일정을 지우지 못했어요. 잠시 뒤 다시 해 주세요.'),
        }
      : {};

    const f = s.f || {};
    const isC = (f.t || 'c') === 'c';
    const setF = (k) => (ev) => this.setState({ f: { ...this.state.f, [k]: ev.target.value } });
    const opts = elderOpts(app);
    const fMon = mondayOf(parseYmd(f.day || s.day));
    const save = () => {
      const ff = this.state.f;
      const body = { date: ff.day || s.day, time: ff.time || null, place: (ff.place || '').trim() || null };
      if (ff.t === 'p') {
        Object.assign(body, { kind: 'OTHER', title: (ff.title || '').trim() || '개인 일정' });
      } else {
        const caseId = ff.elder || (opts[0] && opts[0].v);
        if (!caseId) {
          this.setState({ err: '어르신을 먼저 골라 주세요.' });
          return;
        }
        Object.assign(body, { kind: 'CONSULT', consult_type: CONSULT_CODE[ff.ctype] || 'REGULAR', case_id: caseId });
      }
      const id = s.sheet && s.sheet.id;
      const old = id ? items.find((e) => e.id === id) : null;
      if (!id && ff.t === 'p') body.category = 'ETC';
      // 고칠 때 종류가 바뀌면 반대쪽 칸을 비운다. 개인 일정은 원래 분류를 둔다.
      if (old && ff.t === 'p') Object.assign(body, { consult_type: null, case_id: null, category: old.category || 'ETC' });
      if (old && ff.t !== 'p') Object.assign(body, { title: null, category: null });
      const day = body.date;
      this.run(() => (id ? schedule.update(id, body) : schedule.create(body)), { sheet: null }, '일정을 저장하지 못했어요. 잠시 뒤 다시 해 주세요.', () => pick(day));
    };

    return {
      ...base,
      stop,
      monthLabel: dayKey(mon) === thisMon ? `${g.year}년 ${g.month + 1}월 · 이번 주` : `${mon.getMonth() + 1}/${mon.getDate()} 주`,
      days,
      cells,
      dows: DOW,
      calMonth: `${g.year}년 ${g.month + 1}월`,
      goToday: () => pick(this.state.today),
      dayLabel: label(sel),
      evs,
      noEv: evs.length === 0 && !sched.loading,
      shView: !!(s.sheet && s.sheet.mode === 'view' && cur),
      shClose: () => this.setState({ sheet: null, ask: false, err: '' }),
      v,
      openAdd: () =>
        this.setState({
          sheet: { mode: 'form', id: null }, err: '',
          f: { t: 'c', elder: opts[0] ? opts[0].v : '', ctype: '정기상담', title: '', day: s.day, time: '10:00', place: '' },
        }),
      kindC: () => this.setState({ f: { ...f, t: 'c', elder: f.elder || (opts[0] ? opts[0].v : '') } }),
      kindP: () => this.setState({ f: { ...f, t: 'p' } }),
      f,
      elderOpts: opts,
      dayOpts: DOW.map((d, k) => {
        const x = addDays(fMon, k);
        return { v: dayKey(x), label: `${x.getMonth() + 1}/${x.getDate()} (${d})` };
      }),
      setChild: setF('elder'), setCtype: setF('ctype'), setTitle: setF('title'), setDay: setF('day'), setTime: setF('time'), setPlace: setF('place'),
      save: () => {
        if (!this.state.busy) save();
      },
      msg: s.err || sched.error || app.eldersErr || '',
    };
  }

  run(call, ok, fb, after) {
    if (this.state.busy) return;
    this.setState({ busy: true, err: '' });
    call().then(
      () => {
        this.setState({ busy: false, ...ok });
        this.props.sched.reload();
        if (after) after();
      },
      (e) => this.setState({ busy: false, err: (e && e.message) || fb }),
    );
  }
}

export default function AppSchedule(props) {
  const app = useAppData();
  const [day, setDay] = useState(dayKey(new Date()));
  const g = monthGrid(day);
  const sched = useAppSchedule(!!app.userId, dayKey(g.start), dayKey(g.end));
  const v = useDC(Logic, { ...props, app, sched, setDay });
  return <View v={v} />;
}
