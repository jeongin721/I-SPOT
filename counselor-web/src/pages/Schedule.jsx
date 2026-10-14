// 일정 · 월간 달력 + 일정 추가
// 원본: 다솔 님 디자인 counselor-web-design/Schedule.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './Schedule.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    const now = new Date();
    const inOct = now.getFullYear() === 2026 && now.getMonth() === 9;
    const C = (d, time, title, sub) => ({ y: 2026, m: 9, d, time, t: 'c', title, sub, tag: '상담' });
    const P = (d, time, title, sub) => ({ y: 2026, m: 9, d, time, t: 'p', title, sub, tag: sub });
    this.state = {
      y: 2026,
      m: 9,
      sel: inOct ? now.getDate() : 8,
      filter: 'all',
      adding: false,
      kind: 'c',
      form: { child: '서윤', ctype: '정기상담', pcat: '기관 회의', title: '', time: '10:00', place: '', imp: false },
      events: [
        C(2, '15:00', '서윤 · 정기상담 8회차', '가정 방문'),
        P(5, '10:00', '기관 사례회의', '기관 회의'),
        C(6, '11:00', '도현 · 정기상담 6회차', '면담실 A'),
        C(7, '14:00', '예린 · 정기상담 4회차', '면담실 B'),
        P(8, '10:00', '기관 사례회의', '기관 회의'),
        C(8, '13:00', '지호 · 정기상담 4회차', '면담실 A'),
        C(8, '14:30', '서준 · 초기면담', '가정 방문'),
        C(8, '16:00', '서윤 · 정기상담 9회차', '면담실 B'),
        P(8, '17:30', '슈퍼비전', '슈퍼비전'),
        P(12, '09:30', '아동학대 대응 교육', '교육'),
        C(12, '11:00', '도현 · 정기상담 7회차', '면담실 A'),
        C(13, '16:00', '하은 · 전화상담', '전화'),
        { ...C(14, '15:00', '시우 · 종결 상담', '면담실 A'), imp: true },
        C(15, '15:00', '하린 · 정기상담', '면담실 B'),
        C(16, '14:00', '서윤 · 정기상담 10회차', '면담실 B'),
        P(19, '종일', '연가', '휴가'),
        C(20, '10:00', '유나 · 방문상담', '가정 방문'),
        { ...P(21, '14:00', '경찰 · 지자체 합동 회의', '기관 회의'), imp: true },
        C(22, '13:00', '지호 · 정기상담 5회차', '면담실 A'),
        P(23, '15:00', '팀 회의', '기관 회의'),
        P(26, '10:00', '기관 사례회의', '기관 회의'),
        C(27, '16:00', '도현 · 정기상담 8회차', '면담실 A'),
        P(29, '10:00', '슈퍼비전', '슈퍼비전'),
        C(29, '14:00', '민준 · 정기상담', '면담실 B'),
      ],
    };
  }
  renderVals() {
    const s = this.state;
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    const holidays = { '2026-9-3': '개천절', '2026-9-9': '한글날' };
    const now = new Date();
    const first = new Date(s.y, s.m, 1).getDay();
    const dim = new Date(s.y, s.m + 1, 0).getDate();
    const total = Math.ceil((first + dim) / 7) * 7;
    const show = (e) => s.filter === 'all' || (s.filter === 'i' ? !!e.imp : e.t === s.filter);
    const sortT = (a, b) => (a.time === '종일' ? -1 : b.time === '종일' ? 1 : a.time.localeCompare(b.time));
    const style = (e) =>
      e.imp
        ? {
            bg: '#F7E4DF',
            fg: '#A33B2E',
            dot: '#A33B2E',
            radius: e.t === 'c' ? '50%' : '2px',
            tagBg: '#F7E4DF',
            tagFg: '#A33B2E',
            fw: 700,
          }
        : e.t === 'c'
          ? { bg: '#F2EFE8', fg: '#2B2A26', dot: '#7A776F', radius: '50%', tagBg: '#F2EFE8', tagFg: '#66625A', fw: 400 }
          : {
              bg: '#F7F6F2',
              fg: '#66625A',
              dot: '#B9B2A2',
              radius: '2px',
              tagBg: '#F7F6F2',
              tagFg: '#66625A',
              fw: 400,
            };
    const cells = [];
    for (let i = 0; i < total; i++) {
      const d = i - first + 1;
      const valid = d >= 1 && d <= dim;
      const dow = i % 7;
      const evs = valid ? s.events.filter((e) => e.y === s.y && e.m === s.m && e.d === d && show(e)).sort(sortT) : [];
      const isToday = valid && now.getFullYear() === s.y && now.getMonth() === s.m && now.getDate() === d;
      const isSel = valid && d === s.sel;
      const hol = valid ? holidays[`${s.y}-${s.m}-${d}`] || '' : '';
      cells.push({
        num: valid ? String(d) : '',
        holiday: hol,
        aria: valid ? `${s.m + 1}월 ${d}일 일정 ${evs.length}건` : '빈 칸',
        bg: valid ? (isSel ? '#F1EADA' : '#FFFFFF') : '#F7F6F2',
        ring: isSel ? 'inset 0 0 0 2px #2B2A26' : 'none',
        numBg: isToday ? '#2B2A26' : 'transparent',
        numFg: isToday ? '#FFFFFF' : hol || dow === 0 ? '#7A776F' : '#2B2A26',
        fw: isToday || isSel ? 700 : 400,
        pills: evs.slice(0, 3).map((e) => {
          const st = style(e);
          return {
            label: `${e.time === '종일' ? '' : e.time + ' '}${e.title}`,
            bg: st.bg,
            fg: st.fg,
            fw: st.fw,
            dot: st.dot,
            radius: st.radius,
          };
        }),
        more: evs.length > 3 ? `+${evs.length - 3}건 더` : '',
        pick: () => {
          if (valid) this.setState({ sel: d });
        },
      });
    }
    const selDate = new Date(s.y, s.m, s.sel);
    const dayEvents = s.events
      .map((e, i) => ({ ...e, i }))
      .filter((e) => e.y === s.y && e.m === s.m && e.d === s.sel && show(e))
      .sort(sortT)
      .map((e) => {
        const st = style(e);
        const on = !!e.imp;
        return {
          time: e.time,
          title: e.title,
          sub: e.sub,
          tag: e.tag,
          dot: st.dot,
          radius: st.radius,
          tagBg: st.tagBg,
          tagFg: st.tagFg,
          fw: on ? 700 : 500,
          titleFg: on ? '#A33B2E' : '#2B2A26',
          impOn: on ? 'true' : 'false',
          impLabel: on ? '! 중요' : '중요 표시',
          impBg: on ? '#A33B2E' : '#FFFFFF',
          impFg: on ? '#FFFFFF' : '#7A776F',
          impBd: on ? '#A33B2E' : '#DAD5C9',
          toggleImp: () => this.setState({ events: s.events.map((x, j) => (j === e.i ? { ...x, imp: !x.imp } : x)) }),
        };
      });
    const monthEv = s.events.filter((e) => e.y === s.y && e.m === s.m);
    const setF = (k) => (ev) => this.setState({ form: { ...s.form, [k]: ev.target.value } });
    const isC = s.kind === 'c';
    return {
      monthLabel: `${s.y}년 ${s.m + 1}월`,
      cells,
      dayEvents,
      noEvents: dayEvents.length === 0,
      selLabel: `${s.m + 1}월 ${s.sel}일 ${days[selDate.getDay()]}요일`,
      countC: monthEv.filter((e) => e.t === 'c').length,
      countP: monthEv.filter((e) => e.t === 'p').length,
      countI: monthEv.filter((e) => e.imp).length,
      fAllCls: s.filter === 'all' ? 'on' : '',
      fCCls: s.filter === 'c' ? 'on' : '',
      fPCls: s.filter === 'p' ? 'on' : '',
      fICls: s.filter === 'i' ? 'on' : '',
      showAll: () => this.setState({ filter: 'all' }),
      showC: () => this.setState({ filter: 'c' }),
      showP: () => this.setState({ filter: 'p' }),
      showI: () => this.setState({ filter: 'i' }),
      prevMonth: () => {
        const m = s.m === 0 ? 11 : s.m - 1;
        const y = s.m === 0 ? s.y - 1 : s.y;
        this.setState({ m, y, sel: 1 });
      },
      nextMonth: () => {
        const m = s.m === 11 ? 0 : s.m + 1;
        const y = s.m === 11 ? s.y + 1 : s.y;
        this.setState({ m, y, sel: 1 });
      },
      goToday: () => {
        const n = new Date();
        this.setState({ y: n.getFullYear(), m: n.getMonth(), sel: n.getDate() });
      },
      adding: s.adding,
      notAdding: !s.adding,
      openAdd: () => this.setState({ adding: true }),
      cancelAdd: () => this.setState({ adding: false }),
      isC,
      isP: !isC,
      kindC: () => this.setState({ kind: 'c' }),
      kindP: () => this.setState({ kind: 'p' }),
      kcBorder: isC ? '#2B2A26' : '#DAD5C9',
      kcBg: isC ? '#F1EADA' : '#FFFFFF',
      kpBorder: !isC ? '#2B2A26' : '#DAD5C9',
      kpBg: !isC ? '#F1EADA' : '#FFFFFF',
      form: s.form,
      formImpOn: s.form.imp ? 'true' : 'false',
      formImpBd: s.form.imp ? '#A33B2E' : '#DAD5C9',
      formImpBg: s.form.imp ? '#F7E4DF' : '#FFFFFF',
      formImpFg: s.form.imp ? '#A33B2E' : '#66625A',
      formImpBox: s.form.imp ? '#A33B2E' : '#FFFFFF',
      formImpMark: s.form.imp ? '✓' : '',
      toggleFormImp: () => this.setState({ form: { ...s.form, imp: !s.form.imp } }),
      setChild: setF('child'),
      setCtype: setF('ctype'),
      setPcat: setF('pcat'),
      setTitle: setF('title'),
      setTime: setF('time'),
      setPlace: setF('place'),
      save: () => {
        const f = s.form;
        const ev = isC
          ? {
              y: s.y,
              m: s.m,
              d: s.sel,
              time: f.time || '10:00',
              t: 'c',
              title: `${f.child} · ${f.ctype}`,
              sub: f.place || '장소 미정',
              tag: '상담',
              imp: f.imp,
            }
          : {
              y: s.y,
              m: s.m,
              d: s.sel,
              time: f.time || '10:00',
              t: 'p',
              title: f.title || f.pcat,
              sub: f.place ? `${f.pcat} · ${f.place}` : f.pcat,
              tag: f.pcat,
              imp: f.imp,
            };
        this.setState({ events: [...s.events, ev], adding: false, form: { ...f, title: '', place: '', imp: false } });
      },
    };
  }
}

export default function Schedule(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-Schedule">
      <div
        className={theme.cls}
        style={{
          minHeight: '1200px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <Sidebar active="Schedule" session={session} />

        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>일정</h1>
            </div>
          </header>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', alignItems: 'flex-start' }}>
            <section
              className="card"
              aria-label="월간 달력"
              style={{ flex: '3 1 620px', minWidth: '0', overflow: 'hidden' }}
            >
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '10px 14px',
                  padding: '16px 18px',
                }}
              >
                <button type="button" className="mnav" aria-label="이전 달" onClick={v.prevMonth}>
                  ‹
                </button>
                <b style={{ fontSize: '20px', minWidth: '120px', textAlign: 'center' }}>{v.monthLabel}</b>
                <button type="button" className="mnav" aria-label="다음 달" onClick={v.nextMonth}>
                  ›
                </button>
                <button type="button" className="btn btn-s" style={{ minHeight: '38px' }} onClick={v.goToday}>
                  오늘
                </button>
                <div role="group" aria-label="일정 종류 보기" className="seg" style={{ marginLeft: 'auto' }}>
                  <button type="button" className={v.fAllCls} onClick={v.showAll}>
                    전체
                  </button>
                  <button type="button" className={v.fCCls} onClick={v.showC}>
                    ● 상담
                  </button>
                  <button type="button" className={v.fPCls} onClick={v.showP}>
                    ■ 개인 · 기관
                  </button>
                  <button type="button" className={v.fICls} onClick={v.showI} style={{ color: '#A33B2E' }}>
                    ! 중요
                  </button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', background: '#F7F6F2' }}>
                <span className="dow">일</span>
                <span className="dow">월</span>
                <span className="dow">화</span>
                <span className="dow">수</span>
                <span className="dow">목</span>
                <span className="dow">금</span>
                <span className="dow">토</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))' }}>
                {(v.cells || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <button
                      type="button"
                      className="cell"
                      onClick={c.pick}
                      aria-label={c.aria}
                      style={{ background: c.bg, boxShadow: c.ring }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '50%',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '13px',
                            fontWeight: c.fw,
                            background: c.numBg,
                            color: c.numFg,
                          }}
                        >
                          {c.num}
                        </span>
                        <span style={{ fontSize: '10px', color: '#7A776F' }}>{c.holiday}</span>
                      </span>
                      {(c.pills || []).map((p, pIndex) => (
                        <Fragment key={pIndex}>
                          <span className="pill" style={{ background: p.bg, color: p.fg, fontWeight: p.fw }}>
                            <span
                              style={{
                                width: '7px',
                                height: '7px',
                                flex: 'none',
                                borderRadius: p.radius,
                                background: p.dot,
                              }}
                            ></span>
                            {p.label}
                          </span>
                        </Fragment>
                      ))}
                      <span style={{ fontSize: '11px', color: '#6E6A62', paddingLeft: '4px' }}>{c.more}</span>
                    </button>
                  </Fragment>
                ))}
              </div>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px 20px',
                  padding: '14px 18px',
                  fontSize: '12px',
                  color: '#66625A',
                  borderTop: '1px solid #EAE7DF',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#7A776F' }}></span>
                  상담 일정 {v.countC}건
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#B9B2A2' }}></span>
                  개인 · 기관 일정 {v.countP}건
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    color: '#A33B2E',
                    fontWeight: '500',
                  }}
                >
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#A33B2E' }}></span>
                  중요 {v.countI}건
                </span>
              </div>
            </section>

            <aside
              className="card"
              aria-label="선택한 날 일정"
              style={{
                flex: '1 1 320px',
                minWidth: '0',
                padding: '20px 22px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              {v.notAdding ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ flex: '1' }}>
                      <div className="note">선택한 날</div>
                      <b style={{ fontSize: '19px' }}>{v.selLabel}</b>
                    </div>
                    <button type="button" className="btn btn-p" onClick={v.openAdd}>
                      + 일정 추가
                    </button>
                  </div>
                  <div>
                    {(v.dayEvents || []).map((e, eIndex) => (
                      <Fragment key={eIndex}>
                        <div className="ev">
                          <span style={{ fontSize: '13px', color: '#66625A' }}>{e.time}</span>
                          <span
                            style={{
                              marginTop: '5px',
                              width: '12px',
                              height: '12px',
                              borderRadius: e.radius,
                              background: e.dot,
                            }}
                          ></span>
                          <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <b style={{ fontWeight: e.fw, color: e.titleFg }}>{e.title}</b>
                            <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                              <span className="chip" style={{ background: e.tagBg, color: e.tagFg }}>
                                {e.tag}
                              </span>
                              <span className="note">{e.sub}</span>
                            </span>
                          </span>
                          <button
                            type="button"
                            className="impb"
                            aria-pressed={e.impOn}
                            onClick={e.toggleImp}
                            style={{ background: e.impBg, color: e.impFg, borderColor: e.impBd }}
                          >
                            {e.impLabel}
                          </button>
                        </div>
                      </Fragment>
                    ))}
                    {v.noEvents ? (
                      <>
                        <p className="note" style={{ margin: '8px 0' }}>
                          일정 없음
                        </p>
                      </>
                    ) : null}
                  </div>
                </>
              ) : null}

              {v.adding ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <b style={{ fontSize: '19px', flex: '1' }}>일정 추가</b>
                    <span className="note">{v.selLabel}</span>
                  </div>
                  <div role="radiogroup" aria-label="일정 종류" style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={v.isC}
                      className="kind"
                      onClick={v.kindC}
                      style={{ borderColor: v.kcBorder, background: v.kcBg }}
                    >
                      <b style={{ fontWeight: '700' }}>● 상담 일정</b>
                    </button>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={v.isP}
                      className="kind"
                      onClick={v.kindP}
                      style={{ borderColor: v.kpBorder, background: v.kpBg }}
                    >
                      <b style={{ fontWeight: '700' }}>■ 개인 · 기관 일정</b>
                    </button>
                  </div>

                  {v.isC ? (
                    <>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">아이 (사례)</span>
                        <select className="in" value={v.form.child} onChange={v.setChild}>
                          <option>서윤</option>
                          <option>지호</option>
                          <option>도현</option>
                          <option>예린</option>
                          <option>하은</option>
                          <option>서준</option>
                          <option>시우</option>
                          <option>하린</option>
                          <option>유나</option>
                          <option>민준</option>
                        </select>
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">상담 유형</span>
                        <select className="in" value={v.form.ctype} onChange={v.setCtype}>
                          <option>정기상담</option>
                          <option>초기면담</option>
                          <option>방문상담</option>
                          <option>전화상담</option>
                          <option>종결 상담</option>
                        </select>
                      </label>
                    </>
                  ) : null}
                  {v.isP ? (
                    <>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">분류</span>
                        <select className="in" value={v.form.pcat} onChange={v.setPcat}>
                          <option>기관 회의</option>
                          <option>사례회의</option>
                          <option>슈퍼비전</option>
                          <option>교육</option>
                          <option>외근</option>
                          <option>휴가</option>
                          <option>기타</option>
                        </select>
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">제목</span>
                        <input
                          className="in"
                          type="text"
                          placeholder="예) 팀 회의"
                          value={v.form.title}
                          onChange={v.setTitle}
                        />
                      </label>
                    </>
                  ) : null}

                  <div style={{ display: 'flex', gap: '10px' }}>
                    <label style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lb">시간</span>
                      <input className="in" type="time" value={v.form.time} onChange={v.setTime} />
                    </label>
                    <label style={{ flex: '1.4', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lb">장소</span>
                      <input
                        className="in"
                        type="text"
                        placeholder="예) 면담실 A"
                        value={v.form.place}
                        onChange={v.setPlace}
                      />
                    </label>
                  </div>

                  {v.isC ? (
                    <>
                      <div
                        style={{
                          padding: '12px 14px',
                          borderRadius: '12px',
                          background: '#F7F6F2',
                          fontSize: '13px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <label style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <input
                            type="checkbox"
                            defaultChecked
                            style={{ width: '16px', height: '16px', accentColor: '#2B2A26' }}
                          />
                          상담 전날 <A to="/PreBriefing">브리핑</A> 자동 준비
                        </label>
                        <span className="note">아이 앱 알림 없음 (보호자 노출 방지)</span>
                      </div>
                    </>
                  ) : null}
                  {v.isP ? (
                    <>
                      <div
                        style={{ padding: '12px 14px', borderRadius: '12px', background: '#F7F6F2', fontSize: '13px' }}
                      >
                        <label style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <input type="checkbox" style={{ width: '16px', height: '16px', accentColor: '#2B2A26' }} />팀
                          일정으로 공유
                        </label>
                      </div>
                    </>
                  ) : null}

                  <button
                    type="button"
                    role="switch"
                    aria-checked={v.formImpOn}
                    onClick={v.toggleFormImp}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      minHeight: '46px',
                      padding: '0 14px',
                      borderRadius: '12px',
                      border: `1.5px solid ${v.formImpBd}`,
                      background: v.formImpBg,
                      color: v.formImpFg,
                      font: 'inherit',
                      fontSize: '14px',
                      fontWeight: '700',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '5px',
                        border: `1.5px solid ${v.formImpBd}`,
                        background: v.formImpBox,
                        color: '#FFFFFF',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                      }}
                    >
                      {v.formImpMark}
                    </span>
                    중요 일정 (빨간색 표시)
                  </button>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-s" onClick={v.cancelAdd}>
                      취소
                    </button>
                    <button type="button" className="btn btn-p" onClick={v.save}>
                      저장
                    </button>
                  </div>
                </>
              ) : null}
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
