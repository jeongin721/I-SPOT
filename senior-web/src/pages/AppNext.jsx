// 상담사 앱(폰) · 다음 상담 준비(브리핑) — 디자인 AppNext.dc.html.
//  - 대상자: 주소의 ?case=. 없으면 오늘부터 4주 안 내 일정 중 가장 가까운 상담의 대상자.
//  - 브리핑: senior-brief(POST — 서버가 그때그때 만든다). 웹 사례 상세 탭1 의 '방문 전 브리핑' 과 같은 값.
//    머리 줄 = 다음 방문(next_visit) · 다음 회차 번호(마지막 회차 + 1).
//  - 먼저 볼 것: '어르신이 남긴 말씀' · '안부 응답 변화' 는 안부 앱 값이라 서버에 없어 '—'. '처음 나온 이야기' 는 가장 최근 생활 · 정서 영역 변화.
//  - 확인할 사항: 아직 안 끝난 확인사항(open_checks). 체크하면 끝남(DONE), 풀면 다시 열림(OPEN) — 웹 탭1 과 같은 동작.
//  - 추가 안부 질문: 브리핑의 확인 초안(check_items) 앞 3개. 서버가 규칙으로 만들었으면 '자동 초안'. 칩은 근거(몇 회차 · 측정).
//  - 이 상담 녹음 시작: 앱 · 녹음으로 이 대상자를 싣고 간다.
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/AppNext.logic';
import { cases } from '@cw/api/endpoints';
import { useAppSchedule } from '@cw/data/useAppSchedule';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useIds, href } from '../data/nav';
import { DASH, md } from '../data/format';
import { useAppData, withApp, nameOf, dayWord, upcoming, dayKey, addDays } from './App.parts';
import View from './AppNext.view';

const soft = (p) => p.catch(() => null);

function basisChip(item) {
  const b = (item.basis || [])[0];
  if (!b) return '확인 초안';
  if (b.kind === 'SESSION' && b.session_number) return `${b.session_number}회차 연계`;
  if (b.kind === 'MEASUREMENT') return '측정 연계';
  if (b.kind === 'PROFILE') return '기본 정보 연계';
  return '확인 초안';
}

class Logic extends withApp(DesignLogic) {
  renderVals() {
    const v = super.renderVals();
    const { data, caseId, checkDone, toggleCheck, loadErr, checkErr } = this.props;
    const d = data || {};
    const brief = d.brief;
    const nv = brief && brief.next_visit;
    const nextNo = (d.lastNo || 0) + 1;
    const name = d.c ? nameOf(d.c) : DASH;
    const change = brief && brief.recent_changes && brief.recent_changes[0];
    const checks = (brief && brief.open_checks) || [];
    const sesNo = d.sesNo || {};
    const qs = ((brief && brief.check_items) || []).slice(0, 3);
    const q = (i) => (qs[i] ? { chip: basisChip(qs[i]), text: qs[i].text } : { chip: DASH, text: DASH });
    const fr = this.stGet('ispot-app-from');
    const doneN = checks.filter((x) => !!checkDone[x.id]).length;
    return {
      ...v,
      backHref: /^#\/App[A-Za-z]+/.test(fr || '') && !fr.startsWith('#/AppNext') ? fr : '#/AppSchedule',
      nextSub: nv ? ` · ${dayWord(nv.date)}${nv.time ? ` ${nv.time}` : ''} · ${nextNo}회차` : ` · 다음 방문 일정 ${DASH}`,
      nextTitle: `${name} 다음 상담 준비`,
      lead1: DASH,
      lead1Src: DASH,
      lead2Q: DASH,
      lead2From: `${DASH} `,
      lead2To: ` ${DASH}`,
      lead2Src: DASH,
      lead3Q: change ? `${change.label}${change.change_note ? ` · ${change.change_note}` : ''}` : DASH,
      lead3: change && change.text ? `"${change.text}"` : DASH,
      lead3Src: change ? `${change.session_number}회차 · ${md(change.date)}` : DASH,
      checks: checks.map((x) => ({
        text: `${x.kind === 'ACTION' ? '[할 일] ' : ''}${x.text}`,
        src: [
          x.source_session_id && sesNo[x.source_session_id] ? `근거 · ${sesNo[x.source_session_id]}회차` : '근거 · 상담사 입력',
          x.due_date ? `기한 ${md(x.due_date)}` : null,
        ].filter(Boolean).join(' · '),
        on: !!checkDone[x.id],
        toggle: (e) => toggleCheck(x.id, e.target.checked),
      })),
      doneN: String(doneN),
      checkTotal: String(checks.length),
      draftChip: brief && brief.source === 'RULE' ? '자동 초안' : 'AI 초안',
      q1: q(0),
      q2: q(1),
      q3: q(2),
      recHref: href('AppRecord', { caseId }),
      goRec: () => {},
      msg: loadErr || checkErr || '',
    };
  }
}

export default function AppNext(props) {
  const app = useAppData();
  const ids = useIds();
  const t0 = new Date();
  // ?case= 가 없으면 가장 가까운 상담의 대상자.
  const sched = useAppSchedule(!!app.userId && !ids.caseId, dayKey(t0), dayKey(addDays(t0, 28)));
  const near = sched.items.find((e) => e.kind === 'CONSULT' && e.case_id && upcoming(e));
  const caseId = ids.caseId || (near ? near.case_id : null);
  const [checkDone, setCheckDone] = useState({});
  const [checkErr, setCheckErr] = useState('');
  const main = useAsync(async () => {
    if (!app.userId || !caseId) return null;
    const [c, brief, page] = await Promise.all([
      cases.get(caseId),
      senior.brief(caseId),
      soft(cases.listSessions(caseId, { page_size: 100 })),
    ]);
    const list = page ? page.items : [];
    return {
      c,
      brief,
      lastNo: list.reduce((a, s) => Math.max(a, s.session_number), 0),
      sesNo: Object.fromEntries(list.map((s) => [s.id, s.session_number])),
    };
  }, [app.userId, caseId]);
  const toggleCheck = (id, on) => {
    setCheckErr('');
    setCheckDone((m) => ({ ...m, [id]: on }));
    senior.updateNextCheck(caseId, id, { status: on ? 'DONE' : 'OPEN' }).catch((e) => {
      setCheckDone((m) => ({ ...m, [id]: !on }));
      setCheckErr((e && e.message) || '확인 표시를 저장하지 못했어요. 잠시 뒤 다시 해 주세요.');
    });
  };
  let loadErr = '';
  if (!caseId && !ids.caseId && !sched.loading) loadErr = '다가오는 상담 일정이 없어요. 대상자 목록에서 대상자를 골라 열어 주세요.';
  else if (main.error) loadErr = main.error.message || '다음 상담 준비를 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, app, caseId, data: main.data, checkDone, toggleCheck, checkErr, loadErr });
  return <View v={v} />;
}
