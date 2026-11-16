// 사례 상세 · 탭2 상담 이력 — 디자인 CaseHistory.dc.html.
//  - 회차 줄: 회차 목록(상태 · 상담 방식) + senior-history(회차별 영역 변화 · 이 회차에서 남긴 확인사항 중 아직 안 끝난 것(open_checks)).
//  - '지금까지 상담': 최근 세 회차 요약(senior-history), 주제 비중은 생활 · 정서 영역별 근거 발화 수 비율(care-domains). AI 판정 아님.
//  - '회차별 세부 신호' 표: care-domains 타임라인(영역 × 회차, 칸 숫자 = 근거 발화 수). 고령자에는 학대 신호 · 위기도가 없다.
//  - 이름은 별칭(실명 열람 기록은 탭1 에서만 남긴다). 서버에 없는 칸(안부 앱 연계 등)은 '—'.
//  - 녹음하기는 Upload 화면으로. '새 상담 등록'은 회차를 만들거나(새 회차) 고른 회차 메모에 덧붙여 저장한다.
import { useDC } from '../dc';
import DesignLogic from '../design/CaseHistory.logic';
import { cases, sessions as sessionsApi, schedule } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, md, ymd } from '../data/format';
import { caseLinks, kindLabel, statusChip, subLine, visitWhen } from './CaseInfo.parts';
import View from './CaseHistory.view';

const soft = (p) => p.catch(() => null);
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const CHANGE_SHORT = { CHANGED: '달라짐', NEW: '처음', SIMILAR: '비슷함', NOT_MENTIONED: '이야기 없음' };

/** 요약 핵심 중 측정 줄이 아닌 첫 말씀. */
function firstPoint(summary) {
  if (!summary) return '';
  const k = (summary.key_points || []).find((x) => x && !x.startsWith('이번 측정'));
  return k || '';
}

class Logic extends DesignLogic {
  renderValsBase() {
    const base = super.renderValsBase();
    const st = this.state;
    const { data, caseId, shell } = this.props;
    const d = data || {};
    const c = d.c;
    const list = d.sessions || []; // 회차 번호 큰 것부터
    const hist = d.history || { entries: [], open_checks: [] };
    const visits = Object.fromEntries((hist.entries || []).filter((e) => e.kind === 'VISIT' && e.session_id).map((e) => [e.session_id, e]));
    const openBy = {};
    (hist.open_checks || []).forEach((x) => {
      if (x.source_session_id) openBy[x.source_session_id] = (openBy[x.source_session_id] || 0) + 1;
    });
    const latest = list[0] || null;
    const links = caseLinks(caseId, latest && latest.id);
    const name = (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;

    const rows = list.map((s) => {
      const e = visits[s.id];
      const doms = (e && e.care_domains) || [];
      const changed = doms.filter((x) => x.change === 'CHANGED').length;
      const fresh = doms.filter((x) => x.change === 'NEW').length;
      const open = openBy[s.id] || 0;
      const parts = [];
      if (changed) parts.push(`달라짐 ${changed}`);
      if (fresh) parts.push(`처음 ${fresh}`);
      if (open) parts.push(`확인 ${open}`);
      const sig = parts.length ? parts.join(' · ') : doms.length ? '변화 없음' : '영역 기록 전';
      const [status, chip] = statusChip(s.status);
      const kind = kindLabel(s.consultation_type);
      return {
        href: href('SessionDetail', { caseId, sessionId: s.id }),
        no: `${s.session_number}회차`,
        date: ymd(s.consulted_at || s.created_at),
        kind,
        kindShort: kind,
        status,
        st: chip,
        sig,
        hasSig: parts.length > 0,
        proc: s.status !== 'APPROVED',
      };
    });
    const ordered = rows.filter((x) => x.proc).concat(rows.filter((x) => !x.proc));
    const all = st.sigOnly ? ordered.filter((x) => x.hasSig) : ordered;

    // 회차별 표: care-domains 타임라인
    const asc = [...list].reverse();
    const ncol = Math.max(8, asc.length);
    const cols = Array.from({ length: ncol }, (_, i) => {
      const s = asc[i];
      return s ? { label: `${s.session_number}회`, href: href('SessionDetail', { caseId, sessionId: s.id }) } : { label: '', href: undefined };
    });
    const tl = (d.timeline && d.timeline.domains) || [];
    const mrows = tl.map((g) => {
      const by = Object.fromEntries(g.entries.map((e) => [e.session_id, e]));
      return {
        type: g.domain === 'MOOD' ? '정서' : '생활',
        name: g.label,
        cells: cols.map((_, i) => {
          const s = asc[i];
          const e = s && by[s.id];
          const n = e && e.change !== 'NOT_MENTIONED' ? (e.segment_ids || []).length || 1 : 0;
          const tip = s
            ? `${s.session_number}회차 · ${g.label} · ${e ? CHANGE_SHORT[e.change] : '기록 없음'}${n ? ` · 근거 발화 ${n}개` : ''}${e && e.change_note ? ` · ${e.change_note}` : ''}`
            : '';
          return {
            pend: false, notPend: true, go: undefined, v: n > 0 ? String(n) : '', tip,
            bg: n >= 2 ? '#66788A' : n === 1 ? '#DDE6EC' : 'transparent', fg: n >= 2 ? '#FFFFFF' : '#1F3A56', ring: 'none',
          };
        }),
      };
    });

    // 지금까지 상담: 최근 세 회차
    const recent3 = asc.slice(-3);
    const phases = recent3.map((s, i) => {
      const e = visits[s.id];
      const quote = firstPoint(e && e.summary);
      return {
        note: `${s.session_number}회차 · ${md(s.consulted_at || s.created_at)}${i === recent3.length - 1 ? ' · 최근' : ''}`,
        title: s.title || `${s.session_number}회차`,
        sub: quote ? `"${quote}"` : '',
      };
    });
    // 주제 비중: 영역별 근거 발화 수 비율
    const counts = tl.map((g) => ({
      label: g.label,
      n: g.entries.reduce((a, e) => a + (e.change === 'NOT_MENTIONED' ? 0 : (e.segment_ids || []).length), 0),
      last: [...g.entries].reverse().find((e) => e.change !== 'NOT_MENTIONED'),
    }));
    const sum = counts.reduce((a, x) => a + x.n, 0);
    const topics = sum
      ? [...counts].sort((a, b) => b.n - a.n).map((x) => {
          const pct = `${Math.round((x.n / sum) * 100)}%`;
          return { label: x.label, width: pct, pct };
        })
      : [{ label: DASH, width: '0%', pct: DASH }];
    const least = sum ? [...counts].sort((a, b) => a.n - b.n)[0] : null;

    return {
      ...base,
      ...shell,
      ...links,
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, d.profile),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${d.next ? visitWhen(d.next.date, d.next.time) : DASH}`,
      caseLabel: `${name} · ${no}`,
      aiChip: list.length ? `AI 분석 · 1~${asc[asc.length - 1].session_number}회차` : `AI 분석 · ${DASH}`,
      phases: phases.length ? phases : [{ note: DASH, title: DASH, sub: '' }],
      topics,
      leastLabel: least ? least.label : DASH,
      leastSrc: least ? (least.last ? `${least.last.session_number}회차 마지막 언급` : '아직 이야기 없음') : DASH,
      appLink: DASH,
      recent: ordered.slice(0, 3),
      all,
      total: rows.length,
      shownCount: `${all.length}개`,
      cols,
      mxCols: `150px repeat(${ncol},minmax(44px,1fr))`,
      mrows,
      loadErr: this.props.loadErr,
    };
  }

  // 새 상담 등록 — 회차 목록을 서버 회차로, 저장은 실제 API 로.
  nsVals() {
    const v = super.nsVals();
    const s = this.state || {};
    const { data, caseId } = this.props;
    const list = (data && data.sessions) || [];
    const nextNo = (list[0] ? list[0].session_number : 0) + 1;
    const today = new Date();
    const ses = s.nsSes || 'new';
    const LIST = [['new', `새 회차 · ${nextNo}회차`, `오늘 ${md(today)} · 새 회차 만들기`]].concat(
      list.map((x) => [x.id, `${x.session_number}회차`, `${md(x.consulted_at || x.created_at)} ${kindLabel(x.consultation_type)}`]),
    );
    const cur = LIST.find((x) => x[0] === ses) || LIST[0];
    const save = () => {
      const body = (this.state.nsBody || '').trim();
      if (!body) {
        this.setState({ nsErr: true });
        return;
      }
      const note = (this.state.nsNote || '').trim();
      const memo = note ? `${body}\n\n[상담사 소견]\n${note}` : body;
      this.setState({ nsSaveErr: '', nsBusy: true });
      let call;
      if (ses === 'new') {
        call = cases.createSession(caseId, { title: `${nextNo}회차 상담`, consulted_at: new Date().toISOString(), memo });
      } else {
        const old = list.find((x) => x.id === ses);
        const prev = old && old.memo ? `${old.memo}\n\n` : '';
        call = sessionsApi.update(ses, { memo: `${prev}${memo}` });
      }
      call.then(
        () => {
          this.setState({ nsDone: true, nsBusy: false });
          if (this.props.reload) this.props.reload();
        },
        (e) => this.setState({ nsBusy: false, nsSaveErr: (e && e.message) || '저장하지 못했어요. 잠시 뒤 다시 해 주세요.' }),
      );
    };
    return {
      ...v,
      nsSessions: LIST.map(([id, label, meta]) => ({ label, meta, on: ses === id ? 'true' : 'false', cls: ses === id ? 'on' : '', pick: () => this.setState({ nsSes: id }) })),
      nsSesLabel: ses === 'new' ? `${nextNo}회차 (새 회차)` : `${cur[1]} · ${cur[2]}`,
      nsSave: () => {
        if (!this.state.nsBusy) save();
      },
      nsClose: () => {
        v.nsClose();
        this.setState({ nsSaveErr: '' });
      },
      nsSaveErr: s.nsSaveErr || '',
    };
  }

  renderVals() {
    const v = super.renderVals();
    return { ...v, recOpen: v.goUpload };
  }
}

export default function CaseHistory(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const t0 = new Date();
    const t1 = new Date(t0.getTime() + 180 * 86400000);
    const [c, profile, page, history, timeline, sched] = await Promise.all([
      cases.get(caseId),
      soft(senior.profile(caseId)),
      soft(cases.listSessions(caseId, { page_size: 100 })),
      soft(senior.history(caseId)),
      soft(senior.domainTimeline(caseId)),
      soft(schedule.list({ from: isoDay(t0), to: isoDay(t1) })),
    ]);
    const sessions = page ? [...page.items].sort((a, b) => b.session_number - a.session_number) : [];
    const now = `${isoDay(t0)} ${String(t0.getHours()).padStart(2, '0')}:${String(t0.getMinutes()).padStart(2, '0')}`;
    const next = ((sched && sched.items) || [])
      .filter((e) => e.case_id === caseId && e.kind === 'CONSULT' && `${e.date} ${e.time || '23:59'}` >= now)
      .sort((a, b) => `${a.date} ${a.time || ''}`.localeCompare(`${b.date} ${b.time || ''}`))[0];
    return { c, profile, sessions, history, timeline, next };
  }, [shell.ready, caseId]);
  let loadErr = '';
  if (!caseId) loadErr = '사례를 고르지 않았어요. 사례 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '상담 이력을 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, shell, caseId, data: main.data, reload: main.reload, loadErr });
  return <View v={v} />;
}
