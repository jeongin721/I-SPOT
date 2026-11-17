// Stats 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Stats.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {
themeRead() {
  const K = 'ispot-theme'; let v = null;
  try { v = window.localStorage.getItem(K); } catch (e) {}
  if (!v) { try { v = window.sessionStorage.getItem(K); } catch (e) {} }
  if (!v) { try { v = window.top.__ispotTheme; } catch (e) {} }
  if (!v) { v = window.__ispotTheme; }
  return v === 'dark';
}
themeWrite(dark) {
  const K = 'ispot-theme'; const v = dark ? 'dark' : 'light';
  try { window.localStorage.setItem(K, v); } catch (e) {}
  try { window.sessionStorage.setItem(K, v); } catch (e) {}
  try { window.top.__ispotTheme = v; } catch (e) {}
  window.__ispotTheme = v;
}
jobRead() { let v = null; try { v = window.localStorage.getItem('ispot-job'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-job'); } catch (e) {} } if (!v) { try { v = window.top.__ispotJob; } catch (e) {} } if (!v) v = window.__ispotJob; try { return v ? JSON.parse(v) : null; } catch (e) { return null; } }
jobPhase() { const j = this.jobRead(); if (!j || !j.t) return ''; const el = Date.now() - j.t; return el < 8000 ? 'run' : el < 11000 ? 'done' : el < 11500 ? 'out' : ''; }
jobWrite(v) { try { window.localStorage.setItem('ispot-job', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-job', v); } catch (e) {} try { window.top.__ispotJob = v; } catch (e) {} window.__ispotJob = v; }
componentDidMount() {
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._ntT); try { document.removeEventListener('mousedown', this._ntDoc); } catch (e) {}
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
ntGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
ntSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
ntRecs() { try { const a = JSON.parse(this.ntGet('ispot-intake') || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
ntSave(a) { this.ntSet('ispot-intake', JSON.stringify(a)); }
ntTasks() { return [[3, '어르신 전화 안부 상담'], [7, '가족(보호자) 상담'], [30, '상담 계획서 작성']]; }
ntReadIds() { try { return JSON.parse(this.ntGet('ispot-noti-read') || '[]'); } catch (e) { return []; } }
ntGo0() { let g = null; try { g = JSON.parse(this.ntGet('ispot-sched-go') || 'null'); } catch (e) {} if (!g || !g.t || Date.now() - g.t > 15000) return null; this.ntSet('ispot-sched-go', ''); return g; }
ntVals() {
  const recs = this.ntRecs(); const read = this.ntReadIds(); const days = ['일', '월', '화', '수', '목', '금', '토'];
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const items = [];
  recs.forEach((r) => this.ntTasks().forEach(([n, task]) => { if ((r.done || {})[n]) return; const due = new Date(r.y, r.m, r.d + n); const diff = Math.round((due - t0) / 86400000); const id = r.id + '-' + n;
    items.push({ id, due, diff, unread: read.indexOf(id) < 0, title: r.child + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (due.getMonth() + 1) + '/' + due.getDate() + '(' + days[due.getDay()] + ')까지', y: due.getFullYear(), m: due.getMonth(), d: due.getDate() }); }));
  items.sort((a, b) => a.due - b.due);
  const unread = items.filter((x) => x.unread).length; const open = !!(this.state && this.state.__ntOpen);
  const markRead = (ids) => { const cur = this.ntReadIds(); this.ntSet('ispot-noti-read', JSON.stringify([...cur, ...ids.filter((i) => cur.indexOf(i) < 0)])); };
  return {
    ntOpen: open, ntExp: open ? 'true' : 'false', ntHasBadge: unread > 0, ntBadge: unread > 9 ? '9+' : String(unread),
    ntLabel: unread > 0 ? '알림 ' + unread + '건 읽지 않음' : '알림',
    ntSub: items.length ? '처리 기한 ' + items.length + '건' : '', ntEmpty: items.length === 0,
    ntToggle: () => this.setState({ __ntOpen: !open }),
    ntReadAll: () => { markRead(items.map((x) => x.id)); this.setState({ __ntTick: Date.now() }); },
    ntItems: items.map((x) => ({ title: x.title, sub: x.sub, cls: x.unread ? 'unread' : 'read',
      dd: x.diff < 0 ? '기한 지남' : x.diff === 0 ? '오늘 마감' : 'D-' + x.diff, ddCls: x.diff <= 0 ? 'urgent' : x.diff <= 2 ? 'soon' : '',
      go: (e) => { markRead([x.id]); this.ntSet('ispot-sched-go', JSON.stringify({ y: x.y, m: x.m, d: x.d, t: Date.now() })); this.setState({ __ntOpen: false, __ntTick: Date.now() }); if (this.schedGo) { if (e && e.preventDefault) e.preventDefault(); this.ntSet('ispot-sched-go', ''); this.schedGo(x.y, x.m, x.d); } } }))
  };
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Stats'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { preset: 'm3', from: '2026-07-13', to: '2026-10-12', cal: false, cy: 2026, cm: 9, pickStage: 0 }; }
dpBuild(k, val, set, minS, maxS, defY) {
  const st = this.state.dp || {}; const open = st.k === k;
  const p = (x) => String(x).padStart(2, '0');
  const parse = (v) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(v || '')); return m ? { y: +m[1], m: +m[2], d: +m[3] } : null; };
  const cur = parse(val); const mn = parse(minS); const mx = parse(maxS);
  const key = (y, m, d) => y * 10000 + m * 100 + d; const mnK = mn ? key(mn.y, mn.m, mn.d) : 0; const mxK = mx ? key(mx.y, mx.m, mx.d) : 99999999;
  const go = (o) => this.setState({ dp: { ...(this.state.dp || {}), ...o } });
  const vy = open && st.y ? st.y : (cur ? cur.y : defY); const vm = open && st.m ? st.m : (cur ? cur.m : 1);
  const mode = open ? (st.mode || 'y') : 'y';
  const years = []; for (let y = mx.y; y >= mn.y; y--) years.push({ label: String(y), id: 'dpy-' + k + '-' + y, cls: y === vy ? 'on' : '', on: y === vy ? 'true' : 'false', pick: () => go({ y, mode: 'm' }) });
  const months = Array.from({ length: 12 }, (_, i) => { const m = i + 1; const dis = key(vy, m, 31) < mnK || key(vy, m, 1) > mxK; const on = cur && cur.y === vy && cur.m === m;
    return { label: m + '월', cls: on ? 'on' : '', dis, pick: () => { if (!dis) go({ m, mode: 'd' }); } }; });
  const first = new Date(vy, vm - 1, 1).getDay(); const last = new Date(vy, vm, 0).getDate();
  const days = []; for (let i = 0; i < first; i++) days.push({ blank: true, real: false });
  for (let d = 1; d <= last; d++) { const kk = key(vy, vm, d); const dis = kk < mnK || kk > mxK; const on = cur && cur.y === vy && cur.m === vm && cur.d === d;
    days.push({ blank: false, real: true, n: d, aria: vy + '년 ' + vm + '월 ' + d + '일', cls: on ? 'on' : '', dis, pick: () => { if (dis) return; set(vy + '-' + p(vm) + '-' + p(d)); this.setState({ dp: {} }); } }); }
  const prevY = vm === 1 ? vy - 1 : vy, prevM = vm === 1 ? 12 : vm - 1, nextY = vm === 12 ? vy + 1 : vy, nextM = vm === 12 ? 1 : vm + 1;
  return { open, exp: open ? 'true' : 'false', isY: mode === 'y', isM: mode === 'm', isD: mode === 'd', listId: 'dpl-' + k,
    toggle: () => { if (open) this.setState({ dp: {} }); else { this._dpScroll = 'dpy-' + k + '-' + (cur ? cur.y : defY); this.setState({ dp: { k, mode: 'y', y: cur ? cur.y : defY, m: cur ? cur.m : 1 } }); } },
    close: () => this.setState({ dp: {} }), toY: () => { this._dpScroll = 'dpy-' + k + '-' + vy; go({ mode: 'y' }); }, toM: () => go({ mode: 'm' }),
    years, months, days, dows: ['일', '월', '화', '수', '목', '금', '토'], yLabel: vy + '년', ymLabel: vy + '년 ' + vm + '월',
    prevDis: key(prevY, prevM, 31) < mnK, nextDis: key(nextY, nextM, 1) > mxK,
    prev: () => go({ y: prevY, m: prevM }), next: () => go({ y: nextY, m: nextM }) };
}
componentDidUpdate() { if (this._dpScroll) { const id = this._dpScroll; this._dpScroll = null; setTimeout(() => { try { const el = document.getElementById(id); if (el && el.parentNode) el.parentNode.scrollTop = el.offsetTop - el.parentNode.offsetTop - 80; } catch (e) {} }, 0); } }
renderValsBase() {
  const s = this.state;
  const TODAY = '2026-10-12';
  // ---- 가상 데이터: 2026-01-01 ~ 오늘, 고정 시드
  let seed = 20261012; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const pick = (w) => { const r = rnd(); let a = 0; for (const [k, p] of w) { a += p; if (r < a) return k; } return w.at(-1)[0]; };
  const TYPES = [['정서·우울', 0.22], ['상실·애도', 0.12], ['고립·외로움', 0.18], ['건강·인지', 0.14], ['가족관계', 0.13], ['경제·주거', 0.09], ['생활 적응', 0.08], ['삶의 정리', 0.04]];
  const AGES = [['65~69세', 0.14], ['70~74세', 0.2], ['75~79세', 0.25], ['80~84세', 0.24], ['85세 이상', 0.17]];
  const ACTORS = [['독거', 0.46], ['부부', 0.3], ['자녀동거', 0.16], ['조손', 0.03], ['기타', 0.05]];
  const SITU = [['본인', 0.18], ['가족', 0.22], ['행정복지센터', 0.24], ['맞춤돌봄 수행기관', 0.2], ['의료기관', 0.08], ['치매안심센터', 0.05], ['기타', 0.03]];
  const SVC = [['노인맞춤돌봄', '어르신'], ['장기요양', '어르신 · 가족'], ['치매안심센터', '어르신 · 가족'], ['정신건강복지센터', '어르신'], ['노인복지관', '어르신'], ['통합돌봄 창구', '어르신 · 가족']];
  const day0 = Date.parse('2026-01-01'), dayN = Date.parse(TODAY);
  const DATA = [];
  for (let t = day0; t <= dayN; t += 864e5) {
    const n = rnd() < 0.35 ? 0 : (rnd() < 0.7 ? 1 : 2);
    for (let i = 0; i < n; i++) {
      const judged = rnd() < 0.78;
      DATA.push({ t, judged, repeat: rnd() < 0.12, type: pick(TYPES), age: pick(AGES), actor: pick(ACTORS), situ: pick(SITU),
        svc: SVC.filter(() => rnd() < 0.42).map((x) => x.at(0)), old: (dayN - t) / 864e5 });
    }
  }
  // 위기도 (별도 시드)
  const RISK = [['일반', 0.45], ['관심', 0.32], ['집중', 0.17], ['위기', 0.06]];
  let ks = 5150; const kr = () => { ks = (ks * 1103515245 + 12345) % 2147483648; return ks / 2147483648; };
  DATA.forEach((d) => { const r = kr(); let x = 0; d.risk = RISK.at(-1)[0]; for (const [k, p] of RISK) { x += p; if (r < x) { d.risk = k; break; } } });
  const iso = (t) => new Date(t).toISOString().slice(0, 10);
  const lo = Date.parse(s.from || '2026-01-01'), hi = Date.parse(s.to || TODAY);
  const a = Math.min(lo, hi), b = Math.max(lo, hi);
  const R = DATA.filter((d) => d.t >= a && d.t <= b);
  const J = R.filter((d) => d.judged);
  const days = Math.round((b - a) / 864e5) + 1;
  const pct = (x, n) => (n ? Math.round(x / n * 1000) / 10 : 0) + '%';
  const count = (arr, key, names) => names.map((nm) => [nm, arr.filter((d) => d[key] === nm).length]);
  // KPI
  const svcAll = J.flatMap((d) => d.svc.map((x) => ({ x, done: d.old > 60 || (d.old > 20 && (d.t / 864e5) % 3 < 2) })));
  const doneN = svcAll.filter((v) => v.done).length;
  const k = { total: R.length, perDay: (R.length / days).toFixed(1), judged: J.length, judgedPct: pct(J.length, R.length), repeat: R.filter((d) => d.repeat).length, services: svcAll.length, donePct: pct(doneN, svcAll.length) };
  // 추이 (62일 이하 주별, 그 외 월별)
  const weekly = days <= 62;
  const bins = [];
  if (weekly) { for (let t = a; t <= b; t += 7 * 864e5) bins.push([t, Math.min(b, t + 6 * 864e5)]); }
  else { let y = new Date(a).getUTCFullYear(), m = new Date(a).getUTCMonth(); while (Date.UTC(y, m, 1) <= b) { bins.push([Math.max(a, Date.UTC(y, m, 1)), Math.min(b, Date.UTC(y, m + 1, 0))]); m++; if (m > 11) { m = 0; y++; } } }
  const tv = bins.map(([x, y]) => R.filter((d) => d.t >= x && d.t <= y).length);
  const tmax = Math.max(1, ...tv);
  const trend = bins.map(([x, y], i) => { const v = tv.at(i); const lab = weekly ? `${new Date(x).getUTCMonth() + 1}/${new Date(x).getUTCDate()}~` : `${new Date(x).getUTCMonth() + 1}월`;
    return { v, h: Math.round(v / tmax * 150) + 'px', label: lab, tip: `${iso(x)} ~ ${iso(y)} · 상담 접수 ${v}건` }; });
  // 주호소 유형
  const tc = count(J, 'type', TYPES.map((x) => x.at(0))).sort((p, q) => q[1] - p[1]);
  const tm = Math.max(1, ...tc.map((x) => x[1]));
  const types = tc.map(([name, v]) => ({ name, v, p: pct(v, J.length), w: Math.round(v / tm * 100) + '%', tip: `${name} ${v}건` }));
  const rc = count(J, 'risk', RISK.map((x) => x.at(0)));
  const rkm = Math.max(1, ...rc.map((x) => x[1]));
  const risks = rc.map(([name, v]) => ({ name, v, p: pct(v, J.length), w: Math.round(v / rkm * 100) + '%', tip: `위기도 ${name} ${v}건` }));
  // 연령 (원형)
  const COLORS = ['#3F72AF', '#B04A2F', '#2C84BA', '#7D62B8', '#3E8A5C'];
  const ac = count(J, 'age', AGES.map((x) => x.at(0)));
  let ang = -Math.PI / 2; const tot = Math.max(1, J.length);
  const ages = ac.map(([name, v], i) => { const sweep = v / tot * Math.PI * 2; const a0 = ang, a1 = ang + sweep; ang = a1;
    const big = sweep > Math.PI ? 1 : 0; const P = (r, t) => `${(100 + r * Math.cos(t)).toFixed(2)} ${(100 + r * Math.sin(t)).toFixed(2)}`;
    const d = v === 0 ? '' : (sweep >= Math.PI * 2 - 1e-6 ? 'M100 10 A90 90 0 1 1 99.99 10 Z' : `M100 100 L${P(90, a0)} A90 90 0 ${big} 1 ${P(90, a1)} Z`);
    return { name, v, p: pct(v, J.length), c: COLORS.at(i), d, tip: `${name} ${v}명 (${pct(v, J.length)})` }; });
  // 가구형태 · 의뢰 경로 (표)
  const actc = count(J, 'actor', ACTORS.map((x) => x.at(0))).sort((p, q) => q[1] - p[1]);
  const am = Math.max(1, ...actc.map((x) => x[1]));
  const actors = actc.map(([name, v]) => { const sub = J.filter((d) => d.actor === name); const sc = count(sub, 'situ', SITU.map((x) => x.at(0))).sort((p, q) => q[1] - p[1]);
    return { name, v, p: pct(v, J.length), w: Math.round(v / am * 100) + '%', top: v ? `${sc.at(0).at(0)} (${sc.at(0).at(1)}건)` : '—' }; });
  // 연계 기관
  const sm = Math.max(1, ...SVC.map(([nm]) => svcAll.filter((x) => x.x === nm).length));
  const svc = SVC.map(([nm, target]) => { const all = svcAll.filter((x) => x.x === nm); const dn = all.filter((x) => x.done).length;
    return { label: nm, target, v: all.length, h: Math.round(all.length / sm * 150) + 'px', tip: `${nm} ${all.length}회`, done: dn, ing: all.length - dn, rate: pct(dn, all.length) }; });

  // 지역별 (어르신 거주 구 기준, 예시 관할)
  const GU = [['남구', 0.36], ['동구', 0.2], ['서구', 0.17], ['북구', 0.15], ['광산구', 0.12]];
  const ORG = { '남구': '빛고을 시니어상담센터', '동구': '빛고을 시니어상담센터', '서구': '온담 시니어상담센터', '광산구': '온담 시니어상담센터', '북구': '북구 시니어상담센터' };
  let rs = 7310; const rr = () => { rs = (rs * 1103515245 + 12345) % 2147483648; return rs / 2147483648; };
  const rpick = (w) => { const r = rr(); let x = 0; for (const [k, p] of w) { x += p; if (r < x) return k; } return w.at(-1)[0]; };
  const RG = DATA.filter((d) => d.judged).map((d) => { const cg = rpick(GU); const pg = rr() < 0.8 ? cg : rpick(GU.filter((g) => g[0] !== cg).map((g) => [g[0], 1 / 4])); return { t: d.t, cg, pg }; }).filter((d) => d.t >= a && d.t <= b);
  const rgMax = Math.max(1, ...GU.map(([g]) => RG.filter((d) => d.cg === g).length));
  const regions = GU.map(([g]) => { const sub = RG.filter((d) => d.cg === g); const v = sub.length;
    return { name: g, org: ORG[g], v, p: pct(v, RG.length), w: Math.round(v / rgMax * 100) + '%', away: sub.filter((d) => d.pg !== g).length, joint: sub.filter((d) => ORG[d.pg] !== ORG[g]).length }; }).sort((p, q) => q.v - p.v);
  const JT = RG.filter((d) => ORG[d.pg] !== ORG[d.cg]);
  const jmap = {}; JT.forEach((d) => { const key = d.cg + '|' + d.pg; jmap[key] = (jmap[key] || 0) + 1; });
  const joints = Object.entries(jmap).sort((p, q) => q[1] - p[1]).slice(0, 5).map(([key, v]) => { const [cg, pg] = key.split('|'); return { cg, co: ORG[cg], pg, po: ORG[pg], v }; });
  // 사례관리 기간 (기간 끝 날짜 기준 관리 중 사례)
  const STAFF = ['이서연', '김도윤', '박지민', '최하늘', '정민서', '한유진'];
  let ms = 4021; const mr = () => { ms = (ms * 1103515245 + 12345) % 2147483648; return ms / 2147483648; };
  const MG = []; for (let i = 0; i < 260; i++) { const st = Date.parse('2024-07-01') + Math.floor(mr() * ((dayN - Date.parse('2024-07-01')) / 864e5)) * 864e5; const dur = (90 + mr() * 600) * 864e5; MG.push({ st, en: st + dur, who: STAFF[Math.floor(mr() * STAFF.length)] }); }
  const OPEN = MG.filter((c) => c.st <= b && c.en > b).map((c) => ({ ...c, mon: (b - c.st) / (864e5 * 30.44) }));
  const BINS = [['3개월 미만', 0, 3], ['3~6개월', 3, 6], ['6개월~1년', 6, 12], ['1년 이상', 12, 999]];
  const bmax = Math.max(1, ...BINS.map(([, x, y]) => OPEN.filter((c) => c.mon >= x && c.mon < y).length));
  const mgBins = BINS.map(([name, x, y]) => { const v = OPEN.filter((c) => c.mon >= x && c.mon < y).length; return { name, v, p: pct(v, OPEN.length), w: Math.round(v / bmax * 100) + '%', tip: `${name} ${v}건` }; });
  const std = Math.max(1, Number(s.mgStd) || 25);
  const avgM = (arr) => (arr.length ? (arr.reduce((x, c) => x + c.mon, 0) / arr.length).toFixed(1) + '개월' : '—');
  const mgStaff = STAFF.map((name) => { const sub = OPEN.filter((c) => c.who === name); const v = sub.length; const r = v / std;
    return { name, v, w: Math.min(100, Math.round(r * 100)) + '%', bar: r > 1 ? '#A33B2E' : '#5FA4D6', state: r > 1 ? `${v - std}건 초과` : r >= 0.9 ? '적정 근접' : '적정', cls: r > 1 ? 'c-hi' : r >= 0.9 ? 'c-mid' : 'c-lo',
      m6: sub.filter((c) => c.mon >= 6).length, y1: sub.filter((c) => c.mon >= 12).length, avg: avgM(sub) }; }).sort((p, q) => q.v - p.v);
  const over = mgStaff.filter((x) => x.v > std).length;
  const mgKpi = [
    { label: '관리 중 사례', v: OPEN.length + '건', note: '상담사 ' + STAFF.length + '명' },
    { label: '평균 관리 기간', v: avgM(OPEN), note: '접수 후 경과' },
    { label: '6개월 이상', v: OPEN.filter((c) => c.mon >= 6).length + '건', note: '1년 이상 ' + OPEN.filter((c) => c.mon >= 12).length + '건' },
    { label: '1인당 평균', v: (OPEN.length / STAFF.length).toFixed(1) + '건', note: over ? '적정 초과 ' + over + '명' : '모두 적정 이내' }
  ];
  const insights = [
    `상담 접수 ${k.total}건 · 하루 평균 ${k.perDay}건`,
    types.length ? `최다 주호소: ${types.at(0).name} ${types.at(0).p}` : '',
    actors.length ? `최다 가구형태: ${actors.at(0).name} ${actors.at(0).p} · 주 의뢰 경로 ${actors.at(0).top.split(' (').at(0)}` : '',
    risks.length && risks.at(-1).v ? `위기도 위기 ${risks.at(-1).v}건 · 109 · 정신건강복지센터 연계 여부 우선 확인 권고` : '',
    RG.length ? `공동사례관리 ${JT.length}건 (사례관리 중 ${pct(JT.length, RG.length)})` : '',
    OPEN.length ? `관리 중 ${OPEN.length}건 중 6개월 이상 ${mgBins[2].v + mgBins[3].v}건${over ? ` · 적정 사례 수 초과 상담사 ${over}명` : ''}` : ''
  ].filter(Boolean);
  // 기간 프리셋 · 달력
  const presets = [['all', '전체', '2026-01-01', TODAY], ['m1', '이번 달', '2026-10-01', TODAY], ['m3', '최근 3개월', '2026-07-13', TODAY], ['custom', '직접 선택', null, null]]
    .map(([v, label, f, t]) => ({ label, cls: s.preset === v ? 'on' : '', pick: () => this.setState(f ? { preset: v, from: f, to: t, cal: false } : { preset: v, cal: true, pickStage: 0 }) }));
  const first = new Date(Date.UTC(s.cy, s.cm, 1)).getUTCDay(), dim = new Date(Date.UTC(s.cy, s.cm + 1, 0)).getUTCDate();
  const cal = [];
  for (let i = 0; i < Math.ceil((first + dim) / 7) * 7; i++) { const dd = i - first + 1; const ok = dd >= 1 && dd <= dim; const t = Date.UTC(s.cy, s.cm, dd);
    const future = t > dayN; const inR = ok && t >= a && t <= b; const edge = ok && (t === a || t === b);
    cal.push({ n: ok ? String(dd) : '', off: !ok || future, aria: ok ? iso(t) : '빈 칸', bg: edge ? '#1F3A56' : (inR ? '#E8F4FC' : 'transparent'), fg: edge ? '#D6ECFA' : (future ? '#B5C8D5' : (inR ? '#1F3A56' : '#1F3A56')), fw: edge ? 700 : 400,
      pick: () => { if (!ok || future) return; const d = iso(t);
        if (s.pickStage === 0) this.setState({ preset: 'custom', from: d, to: d, pickStage: 1 }); else this.setState({ preset: 'custom', from: t < Date.parse(s.from) ? d : s.from, to: t < Date.parse(s.from) ? s.from : d, pickStage: 0 }); } }); }
  const fmt = (t) => `${new Date(t).getUTCFullYear()}.${new Date(t).getUTCMonth() + 1}.${new Date(t).getUTCDate()}`;
  return { presets, from: s.from, to: s.to, rangeLabel: `${fmt(a)} ~ ${fmt(b)} · ${days}일`, showCal: s.cal, calCls: s.cal ? 'btn-p' : 'btn-s',
    toggleCal: () => this.setState({ cal: !s.cal, pickStage: 0 }),
    setFrom: (e) => this.setState({ preset: 'custom', from: e.target.value }), setTo: (e) => this.setState({ preset: 'custom', to: e.target.value }),
    dp: { from: this.dpBuild('from', s.from, (v) => this.setState({ preset: 'custom', from: v }), '2026-01-01', '2026-10-12', 2026), to: this.dpBuild('to', s.to, (v) => this.setState({ preset: 'custom', to: v }), '2026-01-01', '2026-10-12', 2026) },
    calLabel: `${s.cy}년 ${s.cm + 1}월`, cal, pickHint: s.pickStage === 1 ? '종료일 선택' : '',
    calPrev: () => this.setState(s.cm === 0 ? { cy: s.cy - 1, cm: 11 } : { cm: s.cm - 1 }), calNext: () => this.setState(s.cm === 11 ? { cy: s.cy + 1, cm: 0 } : { cm: s.cm + 1 }),
    k, trend, binLabel: weekly ? '주별' : '월별', trendAria: trend.map((t) => `${t.label} ${t.v}건`).join(', '),
    regions, joints, noJoint: joints.length === 0, rgSum: `공동사례관리 ${JT.length}건 · ${pct(JT.length, RG.length)}`, mgAsOf: fmt(b), mgStd: String(std), setMgStd: (e) => this.setState({ mgStd: e.target.value }), mgKpi, mgBins, mgStaff,
    types, risks, ages, ageAria: ages.map((x) => `${x.name} ${x.p}`).join(', '), actors, svc, svcAria: svc.map((x) => `${x.label} ${x.v}회`).join(', '), insights };
}
}
