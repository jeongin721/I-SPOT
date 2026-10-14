// 통계 (기간 직접 선택 · 원형 · 가로/세로 막대 · 표)
// 원본: 다솔 님 디자인 counselor-web-design/Stats.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './Stats.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { preset: 'm3', from: '2026-07-13', to: '2026-10-12', cal: false, cy: 2026, cm: 9, pickStage: 0 };
  }
  renderVals() {
    const s = this.state;
    const TODAY = '2026-10-12';
    // ---- 가상 데이터: 2026-01-01 ~ 오늘, 고정 시드
    let seed = 20261012;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    const pick = (w) => {
      const r = rnd();
      let a = 0;
      for (const [k, p] of w) {
        a += p;
        if (r < a) return k;
      }
      return w.at(-1)[0];
    };
    const TYPES = [
      ['정서', 0.3],
      ['신체', 0.24],
      ['방임', 0.14],
      ['중복', 0.28],
      ['성', 0.04],
    ];
    const AGES = [
      ['0~3세', 0.12],
      ['4~6세', 0.18],
      ['7~9세', 0.25],
      ['10~12세', 0.27],
      ['13~17세', 0.18],
    ];
    const ACTORS = [
      ['친부', 0.42],
      ['친모', 0.33],
      ['부모 모두', 0.07],
      ['대리양육자', 0.1],
      ['친인척', 0.05],
      ['기타', 0.03],
    ];
    const SITU = [
      ['양육 태도 · 방법 부족', 0.4],
      ['사회 · 경제적 스트레스', 0.2],
      ['부부 · 가족 갈등', 0.15],
      ['알코올 · 중독 문제', 0.1],
      ['정신건강 문제', 0.1],
      ['기타', 0.05],
    ];
    const SVC = [
      ['상담 · 교육', '아동 · 보호자'],
      ['심리치료', '아동'],
      ['의료 지원', '아동'],
      ['가족기능 강화', '가족'],
      ['부모교육', '보호자'],
      ['기관 연계', '아동 · 가족'],
    ];
    const day0 = Date.parse('2026-01-01'),
      dayN = Date.parse(TODAY);
    const DATA = [];
    for (let t = day0; t <= dayN; t += 864e5) {
      const n = rnd() < 0.35 ? 0 : rnd() < 0.7 ? 1 : 2;
      for (let i = 0; i < n; i++) {
        const judged = rnd() < 0.78;
        DATA.push({
          t,
          judged,
          repeat: rnd() < 0.12,
          type: pick(TYPES),
          age: pick(AGES),
          actor: pick(ACTORS),
          situ: pick(SITU),
          svc: SVC.filter(() => rnd() < 0.42).map((x) => x.at(0)),
          old: (dayN - t) / 864e5,
        });
      }
    }
    const iso = (t) => new Date(t).toISOString().slice(0, 10);
    const lo = Date.parse(s.from || '2026-01-01'),
      hi = Date.parse(s.to || TODAY);
    const a = Math.min(lo, hi),
      b = Math.max(lo, hi);
    const R = DATA.filter((d) => d.t >= a && d.t <= b);
    const J = R.filter((d) => d.judged);
    const days = Math.round((b - a) / 864e5) + 1;
    const pct = (x, n) => (n ? Math.round((x / n) * 1000) / 10 : 0) + '%';
    const count = (arr, key, names) => names.map((nm) => [nm, arr.filter((d) => d[key] === nm).length]);
    // KPI
    const svcAll = J.flatMap((d) =>
      d.svc.map((x) => ({ x, done: d.old > 60 || (d.old > 20 && (d.t / 864e5) % 3 < 2) })),
    );
    const doneN = svcAll.filter((v) => v.done).length;
    const k = {
      total: R.length,
      perDay: (R.length / days).toFixed(1),
      judged: J.length,
      judgedPct: pct(J.length, R.length),
      repeat: R.filter((d) => d.repeat).length,
      services: svcAll.length,
      donePct: pct(doneN, svcAll.length),
    };
    // 추이 (62일 이하 주별, 그 외 월별)
    const weekly = days <= 62;
    const bins = [];
    if (weekly) {
      for (let t = a; t <= b; t += 7 * 864e5) bins.push([t, Math.min(b, t + 6 * 864e5)]);
    } else {
      let y = new Date(a).getUTCFullYear(),
        m = new Date(a).getUTCMonth();
      while (Date.UTC(y, m, 1) <= b) {
        bins.push([Math.max(a, Date.UTC(y, m, 1)), Math.min(b, Date.UTC(y, m + 1, 0))]);
        m++;
        if (m > 11) {
          m = 0;
          y++;
        }
      }
    }
    const tv = bins.map(([x, y]) => R.filter((d) => d.t >= x && d.t <= y).length);
    const tmax = Math.max(1, ...tv);
    const trend = bins.map(([x, y], i) => {
      const v = tv.at(i);
      const lab = weekly
        ? `${new Date(x).getUTCMonth() + 1}/${new Date(x).getUTCDate()}~`
        : `${new Date(x).getUTCMonth() + 1}월`;
      return { v, h: Math.round((v / tmax) * 150) + 'px', label: lab, tip: `${iso(x)} ~ ${iso(y)} · 접수 ${v}건` };
    });
    // 유형
    const tc = count(
      J,
      'type',
      TYPES.map((x) => x.at(0)),
    ).sort((p, q) => q[1] - p[1]);
    const tm = Math.max(1, ...tc.map((x) => x[1]));
    const types = tc.map(([name, v]) => ({
      name,
      v,
      p: pct(v, J.length),
      w: Math.round((v / tm) * 100) + '%',
      tip: `${name} ${v}건`,
    }));
    // 연령 (원형)
    const COLORS = ['#3F72AF', '#B04A2F', '#C8941E', '#7D62B8', '#3E8A5C'];
    const ac = count(
      J,
      'age',
      AGES.map((x) => x.at(0)),
    );
    let ang = -Math.PI / 2;
    const tot = Math.max(1, J.length);
    const ages = ac.map(([name, v], i) => {
      const sweep = (v / tot) * Math.PI * 2;
      const a0 = ang,
        a1 = ang + sweep;
      ang = a1;
      const big = sweep > Math.PI ? 1 : 0;
      const P = (r, t) => `${(100 + r * Math.cos(t)).toFixed(2)} ${(100 + r * Math.sin(t)).toFixed(2)}`;
      const d =
        v === 0
          ? ''
          : sweep >= Math.PI * 2 - 1e-6
            ? 'M100 10 A90 90 0 1 1 99.99 10 Z'
            : `M100 100 L${P(90, a0)} A90 90 0 ${big} 1 ${P(90, a1)} Z`;
      return { name, v, p: pct(v, J.length), c: COLORS.at(i), d, tip: `${name} ${v}명 (${pct(v, J.length)})` };
    });
    // 행위자 (표)
    const actc = count(
      J,
      'actor',
      ACTORS.map((x) => x.at(0)),
    ).sort((p, q) => q[1] - p[1]);
    const am = Math.max(1, ...actc.map((x) => x[1]));
    const actors = actc.map(([name, v]) => {
      const sub = J.filter((d) => d.actor === name);
      const sc = count(
        sub,
        'situ',
        SITU.map((x) => x.at(0)),
      ).sort((p, q) => q[1] - p[1]);
      return {
        name,
        v,
        p: pct(v, J.length),
        w: Math.round((v / am) * 100) + '%',
        top: v ? `${sc.at(0).at(0)} (${sc.at(0).at(1)}건)` : '—',
      };
    });
    // 서비스
    const sm = Math.max(1, ...SVC.map(([nm]) => svcAll.filter((x) => x.x === nm).length));
    const svc = SVC.map(([nm, target]) => {
      const all = svcAll.filter((x) => x.x === nm);
      const dn = all.filter((x) => x.done).length;
      return {
        label: nm,
        target,
        v: all.length,
        h: Math.round((all.length / sm) * 150) + 'px',
        tip: `${nm} ${all.length}회`,
        done: dn,
        ing: all.length - dn,
        rate: pct(dn, all.length),
      };
    });
    const insights = [
      `신고 접수 ${k.total}건 · 하루 평균 ${k.perDay}건`,
      types.length ? `최다 유형: ${types.at(0).name} ${types.at(0).p}` : '',
      actors.length
        ? `최다 행위자: ${actors.at(0).name} ${actors.at(0).p} · ${actors.at(0).top.split(' (').at(0)}`
        : '',
    ].filter(Boolean);
    // 기간 프리셋 · 달력
    const presets = [
      ['m1', '이번 달', '2026-10-01', TODAY],
      ['m3', '최근 3개월', '2026-07-13', TODAY],
      ['all', '전체', '2026-01-01', TODAY],
      ['custom', '직접 선택', null, null],
    ].map(([v, label, f, t]) => ({
      label,
      cls: s.preset === v ? 'on' : '',
      pick: () => this.setState(f ? { preset: v, from: f, to: t, cal: false } : { preset: v, cal: true, pickStage: 0 }),
    }));
    const first = new Date(Date.UTC(s.cy, s.cm, 1)).getUTCDay(),
      dim = new Date(Date.UTC(s.cy, s.cm + 1, 0)).getUTCDate();
    const cal = [];
    for (let i = 0; i < Math.ceil((first + dim) / 7) * 7; i++) {
      const dd = i - first + 1;
      const ok = dd >= 1 && dd <= dim;
      const t = Date.UTC(s.cy, s.cm, dd);
      const future = t > dayN;
      const inR = ok && t >= a && t <= b;
      const edge = ok && (t === a || t === b);
      cal.push({
        n: ok ? String(dd) : '',
        off: !ok || future,
        aria: ok ? iso(t) : '빈 칸',
        bg: edge ? '#2B2A26' : inR ? '#F1EADA' : 'transparent',
        fg: edge ? '#EADBB5' : future ? '#CFC9BB' : inR ? '#2B2A26' : '#2B2A26',
        fw: edge ? 700 : 400,
        pick: () => {
          if (!ok || future) return;
          const d = iso(t);
          if (s.pickStage === 0) this.setState({ preset: 'custom', from: d, to: d, pickStage: 1 });
          else
            this.setState({
              preset: 'custom',
              from: t < Date.parse(s.from) ? d : s.from,
              to: t < Date.parse(s.from) ? s.from : d,
              pickStage: 0,
            });
        },
      });
    }
    const fmt = (t) => `${new Date(t).getUTCFullYear()}.${new Date(t).getUTCMonth() + 1}.${new Date(t).getUTCDate()}`;
    return {
      presets,
      from: s.from,
      to: s.to,
      rangeLabel: `${fmt(a)} ~ ${fmt(b)} · ${days}일`,
      showCal: s.cal,
      calCls: s.cal ? 'btn-p' : 'btn-s',
      toggleCal: () => this.setState({ cal: !s.cal, pickStage: 0 }),
      setFrom: (e) => this.setState({ preset: 'custom', from: e.target.value }),
      setTo: (e) => this.setState({ preset: 'custom', to: e.target.value }),
      calLabel: `${s.cy}년 ${s.cm + 1}월`,
      cal,
      pickHint: s.pickStage === 1 ? '종료일 선택' : '',
      calPrev: () => this.setState(s.cm === 0 ? { cy: s.cy - 1, cm: 11 } : { cm: s.cm - 1 }),
      calNext: () => this.setState(s.cm === 11 ? { cy: s.cy + 1, cm: 0 } : { cm: s.cm + 1 }),
      k,
      trend,
      binLabel: weekly ? '주별' : '월별',
      trendAria: trend.map((t) => `${t.label} ${t.v}건`).join(', '),
      types,
      ages,
      ageAria: ages.map((x) => `${x.name} ${x.p}`).join(', '),
      actors,
      svc,
      svcAria: svc.map((x) => `${x.label} ${x.v}회`).join(', '),
      insights,
    };
  }
}

export default function Stats(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-Stats">
      <div
        className={theme.cls}
        style={{
          minHeight: '1990px',
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
        <Sidebar active="Stats" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>통계</h1>
            </div>
          </header>

          <section
            className="card"
            aria-label="기간 선택"
            style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}>
              <div role="group" aria-label="빠른 기간" className="seg">
                {(v.presets || []).map((p, pIndex) => (
                  <Fragment key={pIndex}>
                    <button type="button" className={p.cls} onClick={p.pick}>
                      {p.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="note">시작</span>
                <input
                  className="inp"
                  type="date"
                  min="2026-01-01"
                  max="2026-10-12"
                  value={v.from}
                  onChange={v.setFrom}
                  aria-label="시작일"
                />
              </label>
              <span className="note">~</span>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="note">종료</span>
                <input
                  className="inp"
                  type="date"
                  min="2026-01-01"
                  max="2026-10-12"
                  value={v.to}
                  onChange={v.setTo}
                  aria-label="종료일"
                />
              </label>
              <button type="button" className={`btn btn-sm ${v.calCls}`} onClick={v.toggleCal}>
                달력
              </button>
              <span className="brn" style={{ marginLeft: 'auto', fontWeight: '700' }}>
                {v.rangeLabel}
              </span>
            </div>
            {v.showCal ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '24px',
                    paddingTop: '6px',
                    borderTop: '1px solid #EAE7DF',
                  }}
                >
                  <div style={{ flex: '0 1 320px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calPrev} aria-label="이전 달">
                        ‹
                      </button>
                      <b style={{ flex: '1', textAlign: 'center' }}>{v.calLabel}</b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calNext} aria-label="다음 달">
                        ›
                      </button>
                    </div>
                    <div className="cal note" style={{ textAlign: 'center', marginBottom: '2px' }}>
                      <span>일</span>
                      <span>월</span>
                      <span>화</span>
                      <span>수</span>
                      <span>목</span>
                      <span>금</span>
                      <span>토</span>
                    </div>
                    <div className="cal">
                      {(v.cal || []).map((d, dIndex) => (
                        <Fragment key={dIndex}>
                          <button
                            type="button"
                            onClick={d.pick}
                            disabled={d.off}
                            aria-label={d.aria}
                            style={{ background: d.bg, color: d.fg, fontWeight: d.fw }}
                          >
                            {d.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <p className="note" style={{ flex: '1 1 220px', margin: '0', alignSelf: 'center' }}>
                    {v.pickHint}
                  </p>
                </div>
              </>
            ) : null}
          </section>

          <section
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            <div className="card kpi">
              <div className="sub">신고 접수</div>
              <b className="brn">{v.k.total}건</b>
              <div className="note">하루 평균 {v.k.perDay}건</div>
            </div>
            <div className="card kpi">
              <div className="sub">학대 판단 사례</div>
              <b className="brn">{v.k.judged}건</b>
              <div className="note">접수 중 {v.k.judgedPct}</div>
            </div>
            <div className="card kpi">
              <div className="sub">재신고 사례</div>
              <b className="brn">{v.k.repeat}건</b>
            </div>
            <div className="card kpi">
              <div className="sub">서비스 제공</div>
              <b className="brn">{v.k.services}회</b>
              <div className="note">완료율 {v.k.donePct}</div>
            </div>
          </section>

          <section className="card" aria-label="신고 접수" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
              <h2 className="h2">신고 접수 추이</h2>
              <span className="note">{v.binLabel}</span>
            </div>
            <div className="vb" style={{ marginTop: '14px' }} role="img" aria-label={v.trendAria}>
              {(v.trend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <div className="col" title={t.tip}>
                    <span className="note" style={{ color: '#2B2A26' }}>
                      {t.v}
                    </span>
                    <span className="b" style={{ height: t.h }}></span>
                  </div>
                </Fragment>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
              {(v.trend || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <span
                    className="note"
                    style={{ flex: '1', minWidth: '0', textAlign: 'center', overflow: 'hidden', whiteSpace: 'nowrap' }}
                  >
                    {t.label}
                  </span>
                </Fragment>
              ))}
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section
              className="card"
              aria-label="학대 유형별 사례 수"
              style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <h2 className="h2">학대 유형별 사례 수</h2>
              {(v.types || []).map((g, gIndex) => (
                <Fragment key={gIndex}>
                  <div className="hb" title={g.tip}>
                    <span>{g.name}</span>
                    <span className="track">
                      <span style={{ width: g.w }}></span>
                    </span>
                    <span className="note" style={{ color: '#2B2A26' }}>
                      {g.v}건 · {g.p}
                    </span>
                  </div>
                </Fragment>
              ))}
            </section>

            <section className="card" aria-label="아동 연령 비율" style={{ padding: '20px 22px' }}>
              <h2 className="h2">학대 피해 아동 연령 비율</h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '22px', marginTop: '12px' }}>
                <svg viewBox="0 0 200 200" width="190" height="190" role="img" aria-label={v.ageAria}>
                  {(v.ages || []).map((a, aIndex) => (
                    <Fragment key={aIndex}>
                      <path d={a.d} fill={a.c} stroke="#FFFFFF" strokeWidth="2">
                        <title>{a.tip}</title>
                      </path>
                    </Fragment>
                  ))}
                  <circle cx="100" cy="100" r="52" fill="#FFFFFF"></circle>
                  <text x="100" y="96" textAnchor="middle" fontSize="13" fill="#7A776F">
                    피해 아동
                  </text>
                  <text x="100" y="118" textAnchor="middle" fontSize="20" fontWeight="700" fill="#2B2A26">
                    {v.k.judged}명
                  </text>
                </svg>
                <div style={{ flex: '1 1 160px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(v.ages || []).map((a, aIndex) => (
                    <Fragment key={aIndex}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                        <span
                          style={{ width: '12px', height: '12px', borderRadius: '3px', background: a.c, flex: 'none' }}
                        ></span>
                        <span style={{ flex: '1' }}>{a.name}</span>
                        <b>{a.p}</b>
                        <span className="note" style={{ width: '44px', textAlign: 'right' }}>
                          {a.v}명
                        </span>
                      </div>
                    </Fragment>
                  ))}
                </div>
              </div>
            </section>
          </div>

          <section className="card" aria-label="학대 행위자 상황" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">학대 행위자 상황</h2>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '700px' }}>
                <thead>
                  <tr>
                    <th>아동과의 관계</th>
                    <th>건수</th>
                    <th style={{ width: '26%' }}>비율</th>
                    <th>가장 많이 확인된 상황</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.actors || []).map((r, rIndex) => (
                    <Fragment key={rIndex}>
                      <tr>
                        <td>
                          <b style={{ fontWeight: '500' }}>{r.name}</b>
                        </td>
                        <td>{r.v}건</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className="mini" style={{ flex: '1' }}>
                              <span style={{ width: r.w }}></span>
                            </span>
                            <span className="note" style={{ width: '44px' }}>
                              {r.p}
                            </span>
                          </div>
                        </td>
                        <td>{r.top}</td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="서비스 제공 현황" style={{ padding: '20px 22px' }}>
              <h2 className="h2">서비스 제공 현황</h2>
              <div className="vb" style={{ marginTop: '14px', height: '200px' }} role="img" aria-label={v.svcAria}>
                {(v.svc || []).map((t, tIndex) => (
                  <Fragment key={tIndex}>
                    <div className="col" title={t.tip}>
                      <span className="note" style={{ color: '#2B2A26' }}>
                        {t.v}
                      </span>
                      <span className="b" style={{ height: t.h }}></span>
                    </div>
                  </Fragment>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
                {(v.svc || []).map((t, tIndex) => (
                  <Fragment key={tIndex}>
                    <span className="note" style={{ flex: '1', minWidth: '0', textAlign: 'center', lineHeight: '1.3' }}>
                      {t.label}
                    </span>
                  </Fragment>
                ))}
              </div>
            </section>
            <section className="card" aria-label="서비스 진행 표" style={{ overflow: 'hidden' }}>
              <div className="hd">
                <h2 className="h2">서비스 진행 상태</h2>
              </div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>서비스</th>
                    <th>대상</th>
                    <th>완료</th>
                    <th>진행 중</th>
                    <th>완료율</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.svc || []).map((t, tIndex) => (
                    <Fragment key={tIndex}>
                      <tr>
                        <td>{t.label}</td>
                        <td className="note">{t.target}</td>
                        <td>{t.done}</td>
                        <td>{t.ing}</td>
                        <td>
                          <b className="brn">{t.rate}</b>
                        </td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <section
            className="card"
            aria-label="AI 분석"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">AI가 본 이 기간</h2>
              <span className="chip c-ai">AI 초안</span>
            </div>
            {(v.insights || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: '#DAD5C9',
                      marginTop: '8px',
                      flex: 'none',
                    }}
                  ></span>
                  <span>{t}</span>
                </div>
              </Fragment>
            ))}
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
