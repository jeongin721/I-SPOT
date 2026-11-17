// 홈(태블릿) — 디자인 HomeTablet.dc.html. 데이터 · 동작은 데스크톱 Home.jsx 와 같다(그 파일의 계산을 그대로 옮겨 왔다 — Logic 이 export 되지 않아서).
//  - 태블릿 마크업 차이: '진행 중 내담자' 는 숫자만, '긴급 업무' 는 카드 안의 짧은 줄(묶음 · 이름 · 내용)로, 카드를 누르면 첫 긴급 어르신 사례로.
//  - 사이드바 안부 연계 · 후속관리 숫자는 공통 배지 값이 없어 비운다.
//  - 오늘 일정: 일정 API(schedule.list)의 오늘 일정. 상담 일정은 그 사례 CaseInfo 로, 나머지는 일정 화면으로.
//  - 다음 상담까지: 오늘 남은 상담 일정에서 센다. 오늘 없으면 앞으로 7일 안의 첫 상담을 아래 줄에 보인다.
//    '상담 전 브리핑 보기' 는 그 상담 사례의 CaseInfo 브리핑으로(상담이 없으면 사례 목록).
//  - 상단 카드: 고령자 현황(senior-overview). 진행 중 내담자 = counts.total, 미처리 · 긴급 업무 = 확인사항 · 기한 지난 확인사항 ·
//    재방문 필요 · 측정 30일 지남(서버에 있는 것만). 서버 값을 못 받으면 '—'.
//  - 알림 종: 디자인은 브라우저에 둔 최초접수 기록을 썼는데, 여기서는 서버의 최초접수 일정(처리 기한 완료 표시 포함)으로 바꾼다.
//  - 고령자에는 위기도 판정이 없어 칩 자리에 돌봄 상태(재방문 필요 등)를 보이고, 없으면 '—'.
import DesignLogic from '../design/HomeTablet.logic';
import { useDC } from '../dc';
import { schedule } from '@cw/api/endpoints';
import { senior, CARE_STATUS_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH } from '../data/format';
import View from './HomeTablet.view';

const pad = (n) => String(n).padStart(2, '0');
const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const toMin = (t) => (t ? Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5)) : null);
const mdOf = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;
// 디자인 일정 추가 창의 상담 유형 이름.
const CONSULT = { REGULAR: '정기상담', INITIAL: '초기상담', VISIT: '방문상담', PHONE: '전화상담', CLOSING: '종결 상담' };
const CATEGORY = {
  AGENCY_MEETING: '기관 회의', CASE_MEETING: '사례회의', INTAKE: '최초접수', SUPERVISION: '슈퍼비전',
  TRAINING: '교육', FIELD_WORK: '외근', LEAVE: '휴가', ETC: '기타',
};
const who = (e) => (e.child_alias ? `${e.child_alias} 님` : DASH);

/** 서버 최초접수 일정 → 디자인 알림 종이 쓰는 접수 기록 모양. */
function intakeRecs(items) {
  return (items || [])
    .filter((e) => e.kind === 'OTHER' && e.category === 'INTAKE')
    .map((e) => {
      const [y, m, d] = e.date.split('-').map(Number);
      return { id: e.id, child: who(e), y, m: m - 1, d, time: e.time || '', place: e.place || '', imp: e.important, done: e.deadline_done || {} };
    });
}

class Logic extends DesignLogic {
  ntRecs() {
    const ev = this.props && this.props.events;
    return intakeRecs(ev && ev.data ? ev.data.items : []);
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const { events, overview, shell } = this.props;
    const now = this.state.now;
    const today = isoDay(now);
    const mins = now.getHours() * 60 + now.getMinutes();
    const items = events.data ? events.data.items : [];

    // 오늘 일정(최초접수의 처리 기한은 알림 종에서 본다).
    const todays = items
      .filter((e) => e.date === today)
      .map((e) => {
        const c = e.kind === 'CONSULT';
        const cat = e.category ? CATEGORY[e.category] : '';
        return {
          m: toMin(e.time), t: c ? 'c' : 'p', time: e.time,
          title: c ? `${who(e)} · ${CONSULT[e.consult_type] || DASH}` : e.category === 'INTAKE' ? `${who(e)} · 최초접수` : e.title || cat,
          sub: c ? e.place || '장소 미정' : e.place ? `${cat} · ${e.place}` : cat,
          href: c && e.case_id ? href('CaseInfo', { caseId: e.case_id }) : '#/Schedule',
        };
      })
      .sort((a, b) => (a.m ?? -1) - (b.m ?? -1));
    const hours = base.hours.map((h, i) => {
      const hr = 9 + i;
      // 9시 전 · 종일 일정은 9시 칸에, 18시 뒤는 18시 칸에 둔다(디자인 칸은 9~18시).
      const evs = todays
        .filter((e) => Math.min(18, Math.max(9, e.m === null ? 9 : Math.floor(e.m / 60))) === hr)
        .map((e) => {
          const c = e.t === 'c';
          return { time: e.time || '종일', title: e.title, sub: e.sub, href: e.href, dot: c ? '#66788A' : '#C5D4DE', radius: c ? '50%' : '2px', bg: '#F8FBFD' };
        });
      return { ...h, events: evs };
    });

    // 다음 상담: 오늘 남은 상담, 없으면 이후 7일 안의 첫 상담.
    const consults = items
      .filter((e) => e.kind === 'CONSULT')
      .sort((a, b) => (a.date + (a.time || '')).localeCompare(b.date + (b.time || '')));
    const nextToday = consults.find((e) => e.date === today && e.time && toMin(e.time) > mins);
    const later = consults.find((e) => e.date > today);
    let remain = '오늘 남은 상담 없음';
    let nextTitle = DASH;
    if (nextToday) {
      const d = toMin(nextToday.time) - mins;
      const hh = Math.floor(d / 60);
      const mm = d % 60;
      remain = hh > 0 ? `${hh}시간 ${mm}분 남음` : `${mm}분 남음`;
      nextTitle = `${nextToday.time} ${who(nextToday)} · ${CONSULT[nextToday.consult_type] || DASH}`;
    } else if (later) {
      const t = new Date(now);
      t.setDate(t.getDate() + 1);
      const when = later.date === isoDay(t) ? '내일 첫 상담' : `다음 상담 ${mdOf(later.date)}`;
      nextTitle = `${when}${later.time ? ` ${later.time}` : ''} · ${who(later)} ${CONSULT[later.consult_type] || ''}`.trim();
    } else if (events.loading) {
      remain = DASH;
    }
    const target = nextToday || later;
    const briefHref = target && target.case_id ? href('CaseInfo', { caseId: target.case_id, sec: 'brief' }) : '#/CaseList';
    const quick = base.quick.map((q) => (q.label === '상담 전 브리핑' ? { ...q, href: briefHref } : q));

    // 상단 카드 — 고령자 현황.
    const ov = overview.data;
    const rows = ov ? ov.rows.filter((r) => r.case_status !== 'CLOSED') : [];
    const caseHref = (r) => href('CaseInfo', { caseId: r.case_id });
    const visitText = (vis) => `${vis.date === today ? '오늘' : mdOf(vis.date)}${vis.time ? ` ${vis.time}` : ''} ${CONSULT[vis.consult_type] || '상담'}`;
    const clients = [...rows]
      .sort((a, b) => {
        const ka = a.next_visit ? a.next_visit.date + (a.next_visit.time || '') : '9';
        const kb = b.next_visit ? b.next_visit.date + (b.next_visit.time || '') : '9';
        return ka.localeCompare(kb) || b.open_checks - a.open_checks;
      })
      .slice(0, 3)
      .map((r) => ({
        chip: r.care_status ? CARE_STATUS_LABELS[r.care_status] : DASH,
        cls: r.care_status === 'REVISIT_NEEDED' ? 'chip c-hi' : 'chip c-mid',
        text: `${r.alias} 님 · ${
          r.next_visit ? visitText(r.next_visit) : r.open_checks ? `확인사항 ${r.open_checks}건` : r.last_visit_at ? `최근 방문 ${mdOf(r.last_visit_at)}` : r.measurement_stale ? '측정 30일 지남' : DASH
        }`,
        href: caseHref(r),
      }));

    // 긴급: 기한 지난 확인사항 · 재방문 필요한데 잡힌 일정이 없는 어르신(사례마다 한 줄).
    const urgent = [];
    rows.forEach((r) => {
      if (r.overdue_checks > 0) urgent.push({ chip: '기한 지남', text: `${r.alias} 님 · 확인사항 ${r.overdue_checks}건 기한 지남`, href: caseHref(r) });
      if (r.care_status === 'REVISIT_NEEDED' && !r.next_visit) urgent.push({ chip: '재방문 필요', text: `${r.alias} 님 · 재방문 일정 없음`, href: caseHref(r) });
    });
    // 미처리: 남은 확인사항(기한 전) · 측정 30일 지남 · 재방문 예정(묶음마다 한 줄).
    const group = (list, chip, cls, count) => {
      if (!list.length) return null;
      const first = list[0];
      return { chip, cls, text: `${first.alias} 님${list.length > 1 ? ` 외 ${list.length - 1}명` : ''}`, n: String(count), href: caseHref(first) };
    };
    const openRows = rows.filter((r) => r.open_checks - r.overdue_checks > 0);
    const staleRows = rows.filter((r) => r.measurement_stale);
    const revisitRows = rows.filter((r) => r.care_status === 'REVISIT_NEEDED' && r.next_visit);
    const openN = openRows.reduce((s, r) => s + r.open_checks - r.overdue_checks, 0);
    const todos = [
      group(openRows, '확인사항', 'chip c-sand', openN),
      group(staleRows, '측정 30일 지남', 'chip c-sky', staleRows.length),
      group(revisitRows, '재방문 예정', 'chip c-check', revisitRows.length),
    ].filter(Boolean);

    return {
      ...base, ...shell, hours, remain, nextTitle, briefHref, quick,
      clientCount: ov ? String(ov.counts.total) : DASH,
      clients,
      todoCount: ov ? String(openN + staleRows.length + revisitRows.length) : DASH,
      todos,
      urgentCount: ov ? String(urgent.length) : DASH,
      // 태블릿 긴급 카드는 칩 없이 글 한 줄씩('○○ 님 · 확인사항 1건 기한 지남').
      urgent: urgent.map((r) => ({ ...r, line: r.text })),
      urgentHref: urgent.length ? urgent[0].href : '#/ChildLink',
      navLinkCnt: '',
      navFollowCnt: '',
    };
  }
}

export default function HomeTablet(props) {
  const shell = useShell();
  const events = useAsync(() => {
    if (!shell.ready) return null;
    const to = new Date();
    to.setDate(to.getDate() + 7);
    // 서버가 기간 앞 30일 안의 최초접수도 같이 준다(알림 종의 처리 기한).
    return schedule.list({ from: isoDay(new Date()), to: isoDay(to) });
  }, [shell.ready]);
  const overview = useAsync(() => (shell.ready ? senior.overview() : null), [shell.ready]);
  const v = useDC(Logic, { ...props, events, overview, shell });
  return <View v={v} />;
}
