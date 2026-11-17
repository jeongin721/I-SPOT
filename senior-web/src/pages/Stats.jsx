// 통계 — 디자인 Stats.dc.html. 디자인의 가상 데이터(고정 시드) 대신 서버의 고령자 사례로 셀 수 있는 것만 센다.
//  - 사례: cases.list(subject_type SENIOR, 쪽을 다 모은다 — 상담사는 자기 사례만 온다). 접수일 = 상담 접수일(report_date), 없으면 등록일.
//  - 상담 접수(KPI · 추이): 기간 안에 접수된 사례 수. 사례관리 진행: 그중 진행 중(ACTIVE)인 사례.
//  - 연령대 비율: 진행 중 사례의 출생연도(접수 해 기준 나이). 65세 미만 · 출생연도 없는 사례는 원형에서 뺀다.
//  - 가구형태 · 의뢰 경로: 고령자 정보(senior-profile)의 가구 형태, 의뢰 경로는 등록 때 적은 '의뢰 경로: …' 줄.
//  - 사례관리 기간: 기간 끝 날짜에 진행 중인 사례를 의뢰일(linked_date) → 접수일 → 등록일부터 센다. 상담사별은 담당 상담사 이름.
//  - 셀 원천이 서버에 없는 것은 '—' · 준비 중: 재의뢰, 연계 · 서비스(연계 기록 없음), 주호소 유형(유형 분류 없음),
//    위기도(고령자에는 위기도 판정이 없다), 지역 · 공동사례관리(거주 지역 · 관할 기관 없음), 'AI가 본 이 기간'(AI 요약 없음).
import { useDC } from '../dc';
import DesignLogic from '../design/Stats.logic';
import { cases } from '@cw/api/endpoints';
import { senior, LIVING_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import View from './Stats.view';

const DAY = 864e5;
const soft = (p) => p.catch(() => null);
const p2 = (x) => String(x).padStart(2, '0');
const isoLocal = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
const iso = (t) => new Date(t).toISOString().slice(0, 10);
const TODAY = isoLocal(new Date());
const back = (days) => iso(Date.parse(TODAY) - days * DAY);

const AGES = [['65~69세', 65, 69], ['70~74세', 70, 74], ['75~79세', 75, 79], ['80~84세', 80, 84], ['85세 이상', 85, 200]];
const COLORS = ['#3F72AF', '#B04A2F', '#2C84BA', '#7D62B8', '#3E8A5C'];
// 디자인의 항목 이름(분류 틀)만 쓰고 값은 '—'.
const TYPES = ['정서·우울', '상실·애도', '고립·외로움', '건강·인지', '가족관계', '경제·주거', '생활 적응', '삶의 정리'];
const RISKS = ['일반', '관심', '집중', '위기'];
const SVC = [['노인맞춤돌봄', '어르신'], ['장기요양', '어르신 · 가족'], ['치매안심센터', '어르신 · 가족'], ['정신건강복지센터', '어르신'], ['노인복지관', '어르신'], ['통합돌봄 창구', '어르신 · 가족']];
const BINS = [['3개월 미만', 0, 3], ['3~6개월', 3, 6], ['6개월~1년', 6, 12], ['1년 이상', 12, 999]];

const okDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v || '') && !Number.isNaN(Date.parse(v));
const caseDay = (c) => c.report_date || (c.created_at || '').slice(0, 10);
const startDay = (c) => c.linked_date || c.report_date || (c.created_at || '').slice(0, 10);
const referral = (c) => {
  const m = /의뢰 경로:\s*([^·\n]+)/.exec(c.linked_background || '');
  return m ? m[1].trim() : null;
};

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    const t = new Date(Date.parse(TODAY));
    this.state = { ...this.state, preset: 'm3', from: back(91), to: TODAY, cy: t.getUTCFullYear(), cm: t.getUTCMonth() };
  }

  renderValsBase() {
    const s = this.state;
    const { data } = this.props;
    const all = (data && data.cases) || [];
    const profiles = (data && data.profiles) || {};
    const dayN = Date.parse(TODAY);
    const earliest = all.reduce((m, c) => (caseDay(c) && caseDay(c) < m ? caseDay(c) : m), back(365));
    const MIN = earliest.slice(0, 4) + '-01-01';
    // 치는 중인 글자(올바른 날짜가 아닌 것)는 셈에 넣지 않는다.
    const lo = okDate(s.from) ? Date.parse(s.from) : Date.parse(MIN);
    const hi = okDate(s.to) ? Date.parse(s.to) : dayN;
    const a = Math.min(lo, hi);
    const b = Math.max(lo, hi);
    const days = Math.round((b - a) / DAY) + 1;
    const pct = (x, n) => (n ? Math.round((x / n) * 1000) / 10 : 0) + '%';
    const inR = (c) => {
      const t = Date.parse(caseDay(c));
      return t >= a && t <= b;
    };
    const R = all.filter(inR);
    const J = R.filter((c) => c.status === 'ACTIVE');

    const k = {
      total: data ? R.length : DASH,
      perDay: data ? (R.length / days).toFixed(1) : DASH,
      judged: data ? J.length : DASH,
      judgedPct: data ? pct(J.length, R.length) : DASH,
      repeat: DASH,
      services: DASH,
      donePct: DASH,
    };

    // 추이(62일 이하 주별, 그 밖은 월별) — 디자인 규칙 그대로.
    const weekly = days <= 62;
    const bins = [];
    if (weekly) {
      for (let t = a; t <= b; t += 7 * DAY) bins.push([t, Math.min(b, t + 6 * DAY)]);
    } else {
      let y = new Date(a).getUTCFullYear();
      let m = new Date(a).getUTCMonth();
      while (Date.UTC(y, m, 1) <= b) {
        bins.push([Math.max(a, Date.UTC(y, m, 1)), Math.min(b, Date.UTC(y, m + 1, 0))]);
        m++;
        if (m > 11) {
          m = 0;
          y++;
        }
      }
    }
    const tv = bins.map(([x, y]) => R.filter((c) => Date.parse(caseDay(c)) >= x && Date.parse(caseDay(c)) <= y).length);
    const tmax = Math.max(1, ...tv);
    const trend = bins.map(([x, y], i) => ({
      v: tv[i],
      h: Math.round((tv[i] / tmax) * 150) + 'px',
      label: weekly ? `${new Date(x).getUTCMonth() + 1}/${new Date(x).getUTCDate()}~` : `${new Date(x).getUTCMonth() + 1}월`,
      tip: `${iso(x)} ~ ${iso(y)} · 상담 접수 ${tv[i]}건`,
    }));

    const dashRows = (names, unit) => names.map((name) => ({ name, v: DASH, p: '', w: '0%', tip: `${name} ${DASH}${unit}` }));
    const types = dashRows(TYPES, '');
    const risks = dashRows(RISKS, '');

    // 연령대(진행 중 사례)
    const ageOf = (c) => (c.child_birth_year ? Number(caseDay(c).slice(0, 4)) - Number(c.child_birth_year) : null);
    const counted = J.filter((c) => {
      const x = ageOf(c);
      return x !== null && x >= 65;
    });
    const tot = Math.max(1, counted.length);
    let ang = -Math.PI / 2;
    const ages = AGES.map(([name, lo2, hi2], i) => {
      const v = counted.filter((c) => ageOf(c) >= lo2 && ageOf(c) <= hi2).length;
      const sweep = (v / tot) * Math.PI * 2;
      const a0 = ang;
      const a1 = ang + sweep;
      ang = a1;
      const P = (r, t) => `${(100 + r * Math.cos(t)).toFixed(2)} ${(100 + r * Math.sin(t)).toFixed(2)}`;
      const d = v === 0 ? '' : sweep >= Math.PI * 2 - 1e-6 ? 'M100 10 A90 90 0 1 1 99.99 10 Z' : `M100 100 L${P(90, a0)} A90 90 0 ${sweep > Math.PI ? 1 : 0} 1 ${P(90, a1)} Z`;
      return { name, v, p: pct(v, counted.length), c: COLORS[i], d, tip: `${name} ${v}명 (${pct(v, counted.length)})` };
    });

    // 가구형태(고령자 정보) · 가장 많은 의뢰 경로
    const living = (c) => {
      const p = profiles[c.id];
      return p && p.living_arrangement ? LIVING_LABELS[p.living_arrangement] : '미입력';
    };
    const names = Object.values(LIVING_LABELS).concat(J.some((c) => living(c) === '미입력') ? ['미입력'] : []);
    const ac = names.map((name) => [name, J.filter((c) => living(c) === name)]).sort((x, y) => y[1].length - x[1].length);
    const am = Math.max(1, ...ac.map((x) => x[1].length));
    const actors = ac.map(([name, sub]) => {
      const cnt = {};
      sub.forEach((c) => {
        const r = referral(c);
        if (r) cnt[r] = (cnt[r] || 0) + 1;
      });
      const top = Object.entries(cnt).sort((x, y) => y[1] - x[1])[0];
      return { name, v: sub.length, p: pct(sub.length, J.length), w: Math.round((sub.length / am) * 100) + '%', top: top ? `${top[0]} (${top[1]}건)` : DASH };
    });

    // 사례관리 기간(기간 끝 날짜에 진행 중인 사례)
    const OPEN = all
      .filter((c) => c.status === 'ACTIVE' && Date.parse(startDay(c)) <= b)
      .map((c) => ({ who: c.counselor_name || DASH, mon: (b - Date.parse(startDay(c))) / (DAY * 30.44) }));
    const bmax = Math.max(1, ...BINS.map(([, x, y]) => OPEN.filter((c) => c.mon >= x && c.mon < y).length));
    const mgBins = BINS.map(([name, x, y]) => {
      const v = OPEN.filter((c) => c.mon >= x && c.mon < y).length;
      return { name, v, p: pct(v, OPEN.length), w: Math.round((v / bmax) * 100) + '%', tip: `${name} ${v}건` };
    });
    const std = Math.max(1, Number(s.mgStd) || 25);
    const avgM = (arr) => (arr.length ? (arr.reduce((x, c) => x + c.mon, 0) / arr.length).toFixed(1) + '개월' : DASH);
    const STAFF = [...new Set(OPEN.map((c) => c.who))];
    const mgStaff = STAFF.map((name) => {
      const sub = OPEN.filter((c) => c.who === name);
      const v = sub.length;
      const r = v / std;
      return {
        name, v, w: Math.min(100, Math.round(r * 100)) + '%', bar: r > 1 ? '#A33B2E' : '#5FA4D6',
        state: r > 1 ? `${v - std}건 초과` : r >= 0.9 ? '적정 근접' : '적정', cls: r > 1 ? 'c-hi' : r >= 0.9 ? 'c-mid' : 'c-lo',
        m6: sub.filter((c) => c.mon >= 6).length, y1: sub.filter((c) => c.mon >= 12).length, avg: avgM(sub),
      };
    }).sort((x, y) => y.v - x.v);
    const over = mgStaff.filter((x) => x.v > std).length;
    const mgKpi = [
      { label: '관리 중 사례', v: OPEN.length + '건', note: '상담사 ' + STAFF.length + '명' },
      { label: '평균 관리 기간', v: avgM(OPEN), note: '접수 후 경과' },
      { label: '6개월 이상', v: OPEN.filter((c) => c.mon >= 6).length + '건', note: '1년 이상 ' + OPEN.filter((c) => c.mon >= 12).length + '건' },
      { label: '1인당 평균', v: STAFF.length ? (OPEN.length / STAFF.length).toFixed(1) + '건' : DASH, note: over ? '적정 초과 ' + over + '명' : '모두 적정 이내' },
    ];

    const svc = SVC.map(([label, target]) => ({ label, target, v: DASH, h: '0px', tip: `${label} ${DASH}`, done: DASH, ing: DASH, rate: DASH }));

    // 기간 프리셋 · 달력(오늘 기준)
    const presets = [['all', '전체', MIN, TODAY], ['m1', '이번 달', TODAY.slice(0, 8) + '01', TODAY], ['m3', '최근 3개월', back(91), TODAY], ['custom', '직접 선택', null, null]].map(
      ([v, label, f, t]) => ({
        label, cls: s.preset === v ? 'on' : '',
        pick: () => this.setState(f ? { preset: v, from: f, to: t, cal: false } : { preset: v, cal: true, pickStage: 0 }),
      }),
    );
    const first = new Date(Date.UTC(s.cy, s.cm, 1)).getUTCDay();
    const dim = new Date(Date.UTC(s.cy, s.cm + 1, 0)).getUTCDate();
    const cal = [];
    for (let i = 0; i < Math.ceil((first + dim) / 7) * 7; i++) {
      const dd = i - first + 1;
      const ok = dd >= 1 && dd <= dim;
      const t = Date.UTC(s.cy, s.cm, dd);
      const future = t > dayN;
      const inRange = ok && t >= a && t <= b;
      const edge = ok && (t === a || t === b);
      cal.push({
        n: ok ? String(dd) : '', off: !ok || future, aria: ok ? iso(t) : '빈 칸',
        bg: edge ? '#1F3A56' : inRange ? '#E8F4FC' : 'transparent', fg: edge ? '#D6ECFA' : future ? '#B5C8D5' : '#1F3A56', fw: edge ? 700 : 400,
        pick: () => {
          if (!ok || future) return;
          const d = iso(t);
          if (this.state.pickStage === 0) this.setState({ preset: 'custom', from: d, to: d, pickStage: 1 });
          else {
            const f0 = this.state.from;
            this.setState({ preset: 'custom', from: t < Date.parse(f0) ? d : f0, to: t < Date.parse(f0) ? f0 : d, pickStage: 0 });
          }
        },
      });
    }
    const fmt = (t) => `${new Date(t).getUTCFullYear()}.${new Date(t).getUTCMonth() + 1}.${new Date(t).getUTCDate()}`;
    const maxY = Number(TODAY.slice(0, 4));

    return {
      presets, from: s.from, to: s.to, rangeLabel: `${fmt(a)} ~ ${fmt(b)} · ${days}일`, showCal: s.cal, calCls: s.cal ? 'btn-p' : 'btn-s',
      toggleCal: () => this.setState({ cal: !s.cal, pickStage: 0 }),
      setFrom: (e) => this.setState({ preset: 'custom', from: e.target.value }),
      setTo: (e) => this.setState({ preset: 'custom', to: e.target.value }),
      dp: {
        from: this.dpBuild('from', s.from, (v) => this.setState({ preset: 'custom', from: v }), MIN, TODAY, maxY),
        to: this.dpBuild('to', s.to, (v) => this.setState({ preset: 'custom', to: v }), MIN, TODAY, maxY),
      },
      calLabel: `${s.cy}년 ${s.cm + 1}월`, cal, pickHint: s.pickStage === 1 ? '종료일 선택' : '',
      calPrev: () => this.setState(s.cm === 0 ? { cy: s.cy - 1, cm: 11 } : { cm: s.cm - 1 }),
      calNext: () => this.setState(s.cm === 11 ? { cy: s.cy + 1, cm: 0 } : { cm: s.cm + 1 }),
      k, trend, binLabel: weekly ? '주별' : '월별', trendAria: trend.map((t) => `${t.label} ${t.v}건`).join(', '),
      regions: [{ name: DASH, org: '준비 중', v: DASH, p: '', w: '0%', away: DASH, joint: DASH }],
      joints: [], noJoint: true, noJointText: '준비 중 · 거주 지역 · 관할 기관 정보가 아직 서버에 없어요',
      rgSum: `공동사례관리 ${DASH}`,
      mgAsOf: fmt(b), mgStd: s.mgStd === undefined ? '25' : String(s.mgStd), setMgStd: (e) => this.setState({ mgStd: e.target.value }), mgKpi, mgBins, mgStaff,
      types, risks, ages, ageAria: ages.map((x) => `${x.name} ${x.p}`).join(', '), actors, svc,
      svcAria: svc.map((x) => `${x.label} ${DASH}`).join(', '),
      insights: [this.props.loadErr || '준비 중 · AI 기간 요약은 아직 없어요'],
    };
  }

  renderVals() {
    return { ...super.renderVals(), ...this.props.shell, navLinkCnt: '', navFollowCnt: '' };
  }
}

export default function Stats(props) {
  const shell = useShell();
  const main = useAsync(async () => {
    if (!shell.ready) return null;
    const list = [];
    for (let page = 1; page <= 50; page++) {
      const res = await cases.list({ subject_type: 'SENIOR', page, page_size: 100 });
      list.push(...res.items);
      if (page >= (res.meta.total_pages || 1)) break;
    }
    const profiles = {};
    for (let i = 0; i < list.length; i += 6) {
      await Promise.all(
        list.slice(i, i + 6).map(async (c) => {
          profiles[c.id] = await soft(senior.profile(c.id));
        }),
      );
    }
    return { cases: list, profiles };
  }, [shell.ready]);
  const loadErr = main.error ? main.error.message || '통계를 불러오지 못했어요.' : '';
  const v = useDC(Logic, { ...props, shell, data: main.data, loadErr });
  return <View v={v} />;
}
