// 일정 — 디자인 Schedule.dc.html. 일정 API(@cw/api/endpoints 의 schedule.list/create/update/remove)에 잇는다.
//  - 보는 달(1일~말일)을 받아 온다. 서버가 기간 앞 30일 안의 최초접수도 같이 줘서 처리 기한(3 · 7 · 30일)이 이 달에 걸치면 보인다.
//  - 최초접수의 처리 기한 · 완료 표시는 서버 deadline_done 으로(디자인은 브라우저 저장소). 알림 종도 같은 서버 기록을 쓴다.
//  - 상담 일정은 사례(어르신)와 이어져 있어 자세히 보기의 '어르신' 이 그 사례 CaseInfo 로 간다. 어르신 고르기는 고령자 사례 목록.
//  - 서버 상담 유형은 정기 · 초기 · 방문 · 전화 · 종결 다섯 가지라 디자인의 '내방상담' · '가족 상담' 은 정기상담으로 저장된다.
//    분류의 '복지관 프로그램 연계' 는 서버에 따로 없어 '기타' 로, 제목을 비우면 그 이름을 제목으로 저장한다.
//  - 남이 만든 공유 일정(editable=false)은 고치기 · 지우기 · 중요 표시를 막는다.
import DesignLogic from '../design/Schedule.logic';
import { useEffect } from 'react';
import { useDC } from '../dc';
import { cases, schedule } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH } from '../data/format';
import View from './Schedule.view';

const pad = (n) => String(n).padStart(2, '0');
const isoDay = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;
const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
// 서버 코드 ↔ 디자인 이름.
const CONSULT = { REGULAR: '정기상담', INITIAL: '초기상담', VISIT: '방문상담', PHONE: '전화상담', CLOSING: '종결 상담' };
const CONSULT_CODE = { 정기상담: 'REGULAR', 초기상담: 'INITIAL', 내방상담: 'REGULAR', 방문상담: 'VISIT', 전화상담: 'PHONE', '가족 상담': 'REGULAR', '종결 상담': 'CLOSING' };
const CATEGORY = {
  AGENCY_MEETING: '기관 회의', CASE_MEETING: '사례회의', INTAKE: '최초접수', SUPERVISION: '슈퍼비전',
  TRAINING: '교육', FIELD_WORK: '외근', LEAVE: '휴가', ETC: '기타',
};
const CATEGORY_CODE = {
  '기관 회의': 'AGENCY_MEETING', 사례회의: 'CASE_MEETING', 최초접수: 'INTAKE', 슈퍼비전: 'SUPERVISION',
  '복지관 프로그램 연계': 'ETC', 교육: 'TRAINING', 외근: 'FIELD_WORK', 휴가: 'LEAVE', 기타: 'ETC',
};
const who = (e) => (e.child_alias ? `${e.child_alias} 님` : DASH);
const errText = (e, fallback) => (e && e.message) || fallback;

/** 서버 최초접수 일정 → 디자인 알림 종 · 처리 기한이 쓰는 접수 기록 모양. */
function intakeRecs(items) {
  return (items || [])
    .filter((e) => e.kind === 'OTHER' && e.category === 'INTAKE')
    .map((e) => {
      const [y, m, d] = e.date.split('-').map(Number);
      return { id: e.id, child: who(e), y, m: m - 1, d, time: e.time || '', place: e.place || '', imp: e.important, done: e.deadline_done || {}, src: e };
    });
}

/** 알림 종에서 넘어온 날짜(디자인 ntGo0 과 같은 저장소 · 15초)를 미리 본다 — 없으면 오늘 달로 연다. */
function peekGo() {
  const k = 'ispot-sched-go';
  let v = null;
  try { v = window.localStorage.getItem(k); } catch (e) { /* 없음 */ }
  if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) { /* 없음 */ } }
  if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) { /* 없음 */ } }
  if (!v) v = (window.__ispotSt || {})[k];
  try {
    const g = v ? JSON.parse(v) : null;
    return g && g.t && Date.now() - g.t <= 15000 ? g : null;
  } catch (e) {
    return null;
  }
}

class Logic extends DesignLogic {
  constructor(props) {
    const go = peekGo();
    super(props);
    const n = new Date();
    if (!go) Object.assign(this.state, { y: n.getFullYear(), m: n.getMonth(), sel: n.getDate() });
    this.state.events = [];
    this.state.items = [];
    this.state.err = '';
    this.state.form = { ...this.state.form, child: '', shared: false };
  }

  ntRecs() {
    return intakeRecs(this.state && this.state.items);
  }

  /** 보는 달의 일정을 (아직 안 받았으면) 받아 온다. 화면 컴포넌트가 로그인 뒤 매번 부른다. */
  ensure() {
    const { y, m } = this.state;
    const key = `${y}-${m}`;
    if (this._want === key) return;
    this._want = key;
    schedule.list({ from: isoDay(y, m, 1), to: isoDay(y, m, new Date(y, m + 1, 0).getDate()) }).then(
      (r) => this._want === key && this.setState({ items: r.items }),
      (e) => this._want === key && this.setState({ err: errText(e, '일정을 불러오지 못했어요.') }),
    );
  }

  reload() {
    this._want = null;
    this.ensure();
  }

  /** 쓰기 요청 → 성공하면 다시 받아 오고 patch 를 적용, 실패하면 오류 줄. */
  write(promise, patch) {
    this.setState({ err: '', busy: true });
    return promise.then(
      () => {
        this.setState({ ...(patch || {}), busy: false });
        this.reload();
      },
      (e) => this.setState({ busy: false, err: errText(e, '저장하지 못했어요. 잠시 뒤 다시 해 주세요.') }),
    );
  }

  renderValsBase() {
    const s = this.state;
    const caseOptions = (this.props.caseList.data ? this.props.caseList.data.items : []).map((c) => ({ value: c.id, label: `${c.child_alias || DASH} 님` }));
    const holidays = { '2026-9-3': '개천절', '2026-9-9': '한글날' };
    const now = new Date();
    const first = new Date(s.y, s.m, 1).getDay();
    const dim = new Date(s.y, s.m + 1, 0).getDate();
    const total = Math.ceil((first + dim) / 7) * 7;
    const recs = this.ntRecs();

    // 서버 일정 → 디자인 일정 모양(key 로 서버 일정 · 처리 기한을 가른다).
    const allEv = [];
    s.items.forEach((x) => {
      if (x.kind === 'OTHER' && x.category === 'INTAKE') return;
      const [y, mo, d] = x.date.split('-').map(Number);
      const c = x.kind === 'CONSULT';
      const cat = x.category ? CATEGORY[x.category] : '';
      allEv.push({
        y, m: mo - 1, d, time: x.time || '종일', t: c ? 'c' : 'p', imp: x.important, src: x, key: { id: x.id },
        title: c ? `${who(x)} · ${CONSULT[x.consult_type] || DASH}` : x.title || cat,
        sub: c ? x.place || '장소 미정' : x.place ? `${cat} · ${x.place}` : cat,
        tag: c ? '상담' : cat,
      });
    });
    recs.forEach((r) => {
      allEv.push({ y: r.y, m: r.m, d: r.d, time: r.time || '종일', t: 'p', title: `${r.child} · 최초접수`, sub: r.place ? `최초접수 · ${r.place}` : '최초접수 · 의뢰 접수 후 배정', tag: '최초접수', imp: !!r.imp, rid: r.id, src: r.src, key: { id: r.id } });
      this.ntTasks().forEach(([n, task]) => {
        const dd = new Date(r.y, r.m, r.d + n);
        const done = !!(r.done || {})[n];
        allEv.push({ y: dd.getFullYear(), m: dd.getMonth(), d: dd.getDate(), time: '기한', t: 'p', title: `${done ? '✓ ' : ''}${r.child} · ${task}`, sub: `접수 후 ${n}일 이내 · ${r.m + 1}/${r.d} 접수`, tag: '처리 기한', imp: !done, rid: r.id, dl: n, done, src: r.src, key: { id: r.id, n } });
      });
    });
    const sameKey = (a, b) => !!a && !!b && a.id === b.id && (a.n || 0) === (b.n || 0);
    const show = (e) => s.filter === 'all' || (s.filter === 'i' ? !!e.imp : e.t === s.filter);
    const rk = (t) => (t === '종일' ? 0 : t === '기한' ? 1 : 2);
    const sortT = (a, b) => rk(a.time) - rk(b.time) || a.time.localeCompare(b.time);
    const style = (e) => (e.imp
      ? { bg: '#F7E4DF', fg: '#A33B2E', dot: '#A33B2E', radius: e.t === 'c' ? '50%' : '2px', tagBg: '#F7E4DF', tagFg: '#A33B2E', fw: 700 }
      : e.t === 'c'
        ? { bg: '#ECF5FA', fg: '#1F3A56', dot: '#66788A', radius: '50%', tagBg: '#ECF5FA', tagFg: '#55687A', fw: 400 }
        : { bg: '#F8FBFD', fg: '#55687A', dot: '#A0B0BB', radius: '2px', tagBg: '#F8FBFD', tagFg: '#55687A', fw: 400 });
    const openView = (e) => this.setState({ view: e.key, adding: false, edit: null, delAsk: false });

    const cells = [];
    for (let i = 0; i < total; i++) {
      const d = i - first + 1;
      const valid = d >= 1 && d <= dim;
      const dow = i % 7;
      const evs = valid ? allEv.filter((e) => e.y === s.y && e.m === s.m && e.d === d && show(e)).sort(sortT) : [];
      const isToday = valid && now.getFullYear() === s.y && now.getMonth() === s.m && now.getDate() === d;
      const isSel = valid && d === s.sel;
      const hol = valid ? holidays[`${s.y}-${s.m}-${d}`] || '' : '';
      cells.push({
        num: valid ? String(d) : '',
        holiday: hol,
        aria: valid ? `${s.m + 1}월 ${d}일 일정 ${evs.length}건` : '빈 칸',
        bg: valid ? (isSel ? '#E8F4FC' : '#FFFFFF') : '#F8FBFD',
        ring: isSel ? 'inset 0 0 0 2px #1F3A56' : 'none',
        numBg: isToday ? '#1F3A56' : 'transparent',
        numFg: isToday ? '#FFFFFF' : hol || dow === 0 ? '#66788A' : '#1F3A56',
        fw: isToday || isSel ? 700 : 400,
        pills: evs.slice(0, 3).map((e) => {
          const st = style(e);
          const parts = e.title.split(' · ');
          return {
            label: `${e.time === '종일' ? '' : `${e.time} `}${e.title}`, time: e.time === '종일' ? '' : e.time,
            who: parts.length > 1 ? parts[0] : '', hasHead: e.time !== '종일' || parts.length > 1,
            body: parts.length > 1 ? parts.slice(1).join(' · ') : e.title, title: e.title,
            bg: st.bg, fg: st.fg, fw: st.fw, dot: st.dot, radius: st.radius, tip: `${e.title} · 자세히 보기`,
            open: (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); this.setState({ sel: d }); openView(e); },
          };
        }),
        more: evs.length > 3 ? `+${evs.length - 3}건 더` : '',
        pick: () => { if (valid) this.setState({ sel: d, view: null, delAsk: false }); },
      });
    }

    const selDate = new Date(s.y, s.m, s.sel);
    const canWrite = (e) => !!(e.src && e.src.editable);
    const setImp = (e) => () => {
      if (!canWrite(e)) { this.setState({ err: '다른 상담사가 만든 공유 일정은 고칠 수 없어요.' }); return; }
      this.write(schedule.update(e.src.id, { important: !e.src.important }));
    };
    const setDone = (e) => () => {
      if (!canWrite(e)) { this.setState({ err: '다른 상담사가 만든 일정은 고칠 수 없어요.' }); return; }
      this.write(schedule.update(e.src.id, { deadline_done: { [String(e.dl)]: !e.done } }));
    };
    const dayEvents = allEv.filter((e) => e.y === s.y && e.m === s.m && e.d === s.sel && show(e)).sort(sortT).map((e) => {
      const st = style(e);
      const on = !!e.imp;
      const stop = (fn) => (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); fn(ev); };
      const go = () => openView(e);
      let row = {
        time: e.time, title: e.title, sub: e.sub, tag: e.tag, dot: st.dot, radius: st.radius, tagBg: st.tagBg, tagFg: st.tagFg, fw: on ? 700 : 500, titleFg: on ? '#A33B2E' : '#1F3A56',
        impOn: on ? 'true' : 'false', impLabel: on ? '! 중요' : '중요 표시', impBg: on ? '#A33B2E' : '#FFFFFF', impFg: on ? '#FFFFFF' : '#66788A', impBd: on ? '#A33B2E' : '#C5D4DE',
        toggleImp: setImp(e),
      };
      if (e.dl) {
        const dn = !!e.done;
        row = { ...row, fw: dn ? 500 : 700, titleFg: dn ? '#66788A' : '#A33B2E', impOn: dn ? 'true' : 'false', impLabel: dn ? '✓ 완료' : '완료 표시', impBg: dn ? '#1F3A56' : '#FFFFFF', impFg: dn ? '#FFFFFF' : '#66788A', impBd: dn ? '#1F3A56' : '#C5D4DE', toggleImp: setDone(e) };
      }
      return {
        ...row, toggleImp: stop(row.toggleImp), open: go, aria: `${e.title} 자세히 보기`,
        key: (ev) => { if (ev && (ev.key === 'Enter' || ev.key === ' ')) { if (ev.preventDefault) ev.preventDefault(); go(); } },
      };
    });

    const monthEv = allEv.filter((e) => e.y === s.y && e.m === s.m);
    const setF = (k) => (ev) => this.setState({ form: { ...this.state.form, [k]: ev.target.value } });
    const isC = s.kind === 'c';
    const vItem = s.view ? allEv.find((e) => sameKey(e.key, s.view)) || null : null;
    const dLabel = (e) => `${e.y}년 ${e.m + 1}월 ${e.d}일 ${DAYS[new Date(e.y, e.m, e.d).getDay()]}요일`;
    const caseLink = (src) => (src && src.case_id ? <a href={href('CaseInfo', { caseId: src.case_id })}>{who(src)}</a> : who(src || {}));
    let vVals = {};
    if (vItem) {
      const e = vItem;
      const st = style(e);
      const isDl = !!e.dl;
      const x = e.src;
      const rows = [['날짜', dLabel(e)], ['시간', isDl ? '마감일' : e.time]];
      if (isDl) {
        rows.push(['내용', e.sub]);
        rows.push(['상태', e.done ? '완료' : '진행 전']);
      } else if (e.t === 'c') {
        rows.push(['어르신', caseLink(x)]);
        rows.push(['상담 유형', CONSULT[x.consult_type] || DASH]);
        rows.push(['장소', x.place || DASH]);
      } else {
        if (e.rid) rows.push(['어르신', caseLink(x)]);
        rows.push(['분류', e.tag]);
        rows.push(['장소', x.place || DASH]);
      }
      rows.push(['중요', e.imp ? '중요 일정' : DASH]);
      const ask = !!s.delAsk;
      vVals = {
        kind: isDl ? '처리 기한' : e.t === 'c' ? '상담 일정' : '개인 · 기관 일정', title: e.title, dot: st.dot, radius: st.radius, titleFg: e.imp ? '#A33B2E' : 'inherit',
        rows: rows.map(([k, val]) => ({ k, v: val })), isDl, canEdit: !isDl && canWrite(e), ask, noAsk: !ask,
        askNote: e.rid && !isDl ? '최초접수와 함께 만들어진 처리 기한 일정 3건도 같이 삭제되고, 알림에서도 빠져요.' : '삭제하면 되돌릴 수 없어요.',
        doneLabel: e.done ? '✓ 완료 취소' : '완료 표시', doneCls: e.done ? 'btn-s' : 'btn-p',
        toggleDone: setDone(e),
        goBase: () => {
          const r = recs.find((q) => q.id === e.rid);
          if (r) this.setState({ y: r.y, m: r.m, sel: r.d, view: { id: r.id } });
        },
        askDel: () => this.setState({ delAsk: true }), cancelDel: () => this.setState({ delAsk: false }),
        del: () => this.write(schedule.remove(x.id), { view: null, delAsk: false }),
        edit: () => {
          const c = x.kind === 'CONSULT';
          const isRec = !!e.rid;
          const form = {
            ...s.form, date: x.date, time: x.time || '', imp: !!x.important, place: x.place || '', shared: !!x.shared,
            child: c || isRec ? x.case_id || '' : s.form.child,
            ctype: c ? CONSULT[x.consult_type] || '정기상담' : s.form.ctype,
            pcat: c ? s.form.pcat : CATEGORY[x.category] || '기타',
            title: c || isRec ? '' : x.title || '',
          };
          this.setState({ adding: true, kind: c ? 'c' : 'p', form, edit: { id: x.id, allDay: !x.time, caseHidden: !!x.case_hidden }, delAsk: false, err: '' });
        },
      };
    }

    const f = s.form;
    const isIntake = !isC && f.pcat === '최초접수';
    const save = () => {
      if (s.busy) return;
      const ed = s.edit;
      const needCase = isC || isIntake;
      const keepHidden = ed && ed.caseHidden && !f.child; // 볼 수 없는 사례가 붙은 일정은 사례 칸을 보내지 않는다.
      if (needCase && !f.child && !keepHidden) { this.setState({ err: '어르신(사례)을 골라 주세요.' }); return; }
      const date = ed ? f.date || isoDay(s.y, s.m, s.sel) : isoDay(s.y, s.m, s.sel);
      const body = {
        kind: isC ? 'CONSULT' : 'OTHER', date, time: f.time || (ed && ed.allDay ? null : '10:00'), place: f.place || null, important: !!f.imp,
      };
      if (isC) body.consult_type = CONSULT_CODE[f.ctype] || 'REGULAR';
      else {
        body.category = CATEGORY_CODE[f.pcat] || 'ETC';
        if (!isIntake) {
          body.title = f.title || (f.pcat === '복지관 프로그램 연계' ? f.pcat : null);
          body.shared = !!f.shared;
        }
      }
      if (needCase) { if (!keepHidden) body.case_id = f.child; } else if (!(ed && ed.caseHidden)) body.case_id = null;
      const [Y, M, D] = date.split('-').map(Number);
      const after = { adding: false, edit: null, view: null, y: Y, m: M - 1, sel: D, form: { ...f, title: '', place: '', imp: false, shared: false } };
      this.write(ed ? schedule.update(ed.id, body) : schedule.create(body), after);
    };
    const childDefault = f.child || (caseOptions[0] ? caseOptions[0].value : '');
    const formChild = s.adding ? childDefault : f.child;
    return {
      monthLabel: `${s.y}년 ${s.m + 1}월`,
      cells, dayEvents, noEvents: dayEvents.length === 0,
      selLabel: `${s.m + 1}월 ${s.sel}일 ${DAYS[selDate.getDay()]}요일`,
      countC: monthEv.filter((e) => e.t === 'c').length,
      countP: monthEv.filter((e) => e.t === 'p').length,
      countI: monthEv.filter((e) => e.imp).length,
      fAllCls: s.filter === 'all' ? 'on' : '', fCCls: s.filter === 'c' ? 'on' : '', fPCls: s.filter === 'p' ? 'on' : '', fICls: s.filter === 'i' ? 'on' : '',
      showAll: () => this.setState({ filter: 'all' }), showC: () => this.setState({ filter: 'c' }), showP: () => this.setState({ filter: 'p' }), showI: () => this.setState({ filter: 'i' }),
      prevMonth: () => { const m = s.m === 0 ? 11 : s.m - 1; const y = s.m === 0 ? s.y - 1 : s.y; this.setState({ m, y, sel: 1, view: null }); },
      nextMonth: () => { const m = s.m === 11 ? 0 : s.m + 1; const y = s.m === 11 ? s.y + 1 : s.y; this.setState({ m, y, sel: 1, view: null }); },
      goToday: () => { const n = new Date(); this.setState({ y: n.getFullYear(), m: n.getMonth(), sel: n.getDate(), view: null }); },
      adding: s.adding, notAdding: !s.adding && !vItem, viewing: !s.adding && !!vItem, v: vVals, vBack: () => this.setState({ view: null, delAsk: false }),
      isEdit: !!s.edit, formTitle: s.edit ? '일정 수정' : '일정 추가', formDateLabel: s.edit ? '' : `${s.m + 1}월 ${s.sel}일 ${DAYS[selDate.getDay()]}요일`,
      setDate: setF('date'),
      openAdd: () => this.setState({ adding: true, edit: null, err: '', form: { ...s.form, child: childDefault, title: '', place: '', imp: false, shared: false } }),
      cancelAdd: () => this.setState({ adding: false, edit: null, err: '' }),
      isC, isP: !isC, isIntake, notIntake: !isIntake,
      dlPreview: this.ntTasks().map(([n, task]) => { const dd = new Date(s.y, s.m, s.sel + n); return { n: `${n}일 이내`, task, due: `${dd.getMonth() + 1}/${dd.getDate()}(${DAYS[dd.getDay()]})` }; }),
      kindC: () => this.setState({ kind: 'c' }), kindP: () => this.setState({ kind: 'p' }),
      kcBorder: isC ? '#1F3A56' : '#C5D4DE', kcBg: isC ? '#E8F4FC' : '#FFFFFF',
      kpBorder: !isC ? '#1F3A56' : '#C5D4DE', kpBg: !isC ? '#E8F4FC' : '#FFFFFF',
      form: { ...f, child: formChild },
      caseOptions,
      formBriefHref: formChild ? href('CaseInfo', { caseId: formChild, sec: 'brief' }) : '#/CaseList',
      toggleShared: () => this.setState({ form: { ...this.state.form, shared: !this.state.form.shared } }),
      formImpOn: f.imp ? 'true' : 'false', formImpBd: f.imp ? '#A33B2E' : '#C5D4DE', formImpBg: f.imp ? '#F7E4DF' : '#FFFFFF', formImpFg: f.imp ? '#A33B2E' : '#55687A',
      formImpBox: f.imp ? '#A33B2E' : '#FFFFFF', formImpMark: f.imp ? '✓' : '', toggleFormImp: () => this.setState({ form: { ...this.state.form, imp: !this.state.form.imp } }),
      setChild: setF('child'), setCtype: setF('ctype'), setPcat: setF('pcat'), setTitle: setF('title'), setTime: setF('time'), setPlace: setF('place'),
      save,
      err: s.err,
      ensure: () => this.ensure(),
      ...this.props.shell,
    };
  }
}

export default function Schedule(props) {
  const shell = useShell();
  const caseList = useAsync(() => (shell.ready ? cases.list({ subject_type: 'SENIOR', page_size: 100 }) : null), [shell.ready]);
  const v = useDC(Logic, { ...props, caseList, shell });
  // 로그인이 확인되면 보는 달 일정을 받는다(달을 넘기면 다시 — ensure 가 같은 달은 건너뛴다).
  useEffect(() => {
    if (shell.ready) v.ensure();
  });
  return <View v={v} />;
}
